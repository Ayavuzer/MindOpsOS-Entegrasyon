"""IMAP client with IDLE support for real-time email notifications."""

import asyncio
import logging
import ssl
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Callable, List, Any

import aioimaplib

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """IMAP connection state."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED = "authenticated"
    IDLE = "idle"
    ERROR = "error"


class AuthMethod(Enum):
    """Authentication method."""
    PASSWORD = "password"
    OAUTH2 = "oauth2"


@dataclass
class IMAPConfig:
    """IMAP connection configuration."""
    host: str
    port: int = 993
    use_ssl: bool = True
    auth_method: AuthMethod = AuthMethod.PASSWORD
    
    # Password auth
    username: Optional[str] = None
    password: Optional[str] = None
    
    # OAuth2 auth
    oauth_access_token: Optional[str] = None
    oauth_email: Optional[str] = None
    
    # Connection settings
    timeout_seconds: int = 30
    idle_timeout_seconds: int = 1740  # 29 minutes (RFC recommends <29 min)
    reconnect_delay_seconds: int = 5
    max_reconnect_attempts: int = 10


@dataclass
class EmailNotification:
    """Notification about new email arrival."""
    uid: int
    folder: str
    timestamp: datetime
    subject: Optional[str] = None
    sender: Optional[str] = None


class IMAPIdleClient:
    """IMAP client with IDLE support for real-time notifications."""
    
    def __init__(
        self,
        config: IMAPConfig,
        on_new_email: Optional[Callable[[EmailNotification], Any]] = None,
        on_state_change: Optional[Callable[[ConnectionState], Any]] = None,
    ):
        self.config = config
        self.on_new_email = on_new_email
        self.on_state_change = on_state_change
        
        self._client: Optional[aioimaplib.IMAP4_SSL] = None
        self._state = ConnectionState.DISCONNECTED
        self._running = False
        self._idle_task: Optional[asyncio.Task] = None
        self._reconnect_count = 0
        self._last_seen_uid = 0
    
    @property
    def state(self) -> ConnectionState:
        return self._state
    
    async def _set_state(self, new_state: ConnectionState) -> None:
        """Update state and notify callback."""
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            logger.debug(f"IMAP state: {old_state.value} → {new_state.value}")
            if self.on_state_change:
                try:
                    result = self.on_state_change(new_state)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"State change callback error: {e}")
    
    async def connect(self) -> bool:
        """Establish IMAP connection."""
        try:
            await self._set_state(ConnectionState.CONNECTING)
            
            if self.config.use_ssl:
                ssl_context = ssl.create_default_context()
                self._client = aioimaplib.IMAP4_SSL(
                    host=self.config.host,
                    port=self.config.port,
                    timeout=self.config.timeout_seconds,
                    ssl_context=ssl_context,
                )
            else:
                self._client = aioimaplib.IMAP4(
                    host=self.config.host,
                    port=self.config.port,
                    timeout=self.config.timeout_seconds,
                )
            
            await self._client.wait_hello_from_server()
            await self._set_state(ConnectionState.CONNECTED)
            
            return True
            
        except Exception as e:
            logger.error(f"IMAP connection failed: {e}")
            await self._set_state(ConnectionState.ERROR)
            return False
    
    async def authenticate(self) -> bool:
        """Authenticate with IMAP server."""
        if not self._client:
            return False
        
        try:
            await self._set_state(ConnectionState.AUTHENTICATING)
            
            if self.config.auth_method == AuthMethod.OAUTH2:
                # OAuth2 XOAUTH2 authentication
                if not self.config.oauth_access_token or not self.config.oauth_email:
                    raise ValueError("OAuth2 requires access_token and email")
                
                # Build XOAUTH2 string
                auth_string = f"user={self.config.oauth_email}\x01auth=Bearer {self.config.oauth_access_token}\x01\x01"
                
                response = await self._client.authenticate("XOAUTH2", lambda x: auth_string)
                
            else:
                # Standard password authentication
                if not self.config.username or not self.config.password:
                    raise ValueError("Password auth requires username and password")
                
                response = await self._client.login(
                    self.config.username,
                    self.config.password,
                )
            
            if response.result == "OK":
                await self._set_state(ConnectionState.AUTHENTICATED)
                self._reconnect_count = 0  # Reset on successful auth
                return True
            else:
                logger.error(f"IMAP auth failed: {response}")
                await self._set_state(ConnectionState.ERROR)
                return False
                
        except Exception as e:
            logger.error(f"IMAP authentication error: {e}")
            await self._set_state(ConnectionState.ERROR)
            return False
    
    async def select_folder(self, folder: str = "INBOX") -> bool:
        """Select mailbox folder."""
        if not self._client:
            return False
        
        try:
            response = await self._client.select(folder)
            if response.result == "OK":
                # Get latest UID for tracking new emails
                await self._update_last_seen_uid()
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to select folder {folder}: {e}")
            return False
    
    async def _update_last_seen_uid(self) -> None:
        """Update last seen UID to track new emails."""
        if not self._client:
            return
        
        try:
            response = await self._client.search("ALL")
            if response.result == "OK" and response.lines:
                uids = response.lines[0].decode().split()
                if uids:
                    self._last_seen_uid = int(uids[-1])
        except Exception as e:
            logger.debug(f"Failed to get last UID: {e}")
    
    async def start_idle(self) -> None:
        """Start IDLE loop for real-time notifications."""
        if self._running:
            return
        
        self._running = True
        self._idle_task = asyncio.create_task(self._idle_loop())
    
    async def stop_idle(self) -> None:
        """Stop IDLE loop."""
        self._running = False
        
        if self._idle_task:
            self._idle_task.cancel()
            try:
                await self._idle_task
            except asyncio.CancelledError:
                pass
        
        if self._client:
            try:
                await self._client.logout()
            except Exception:
                pass
        
        await self._set_state(ConnectionState.DISCONNECTED)
    
    async def _idle_loop(self) -> None:
        """Main IDLE loop with reconnection logic."""
        while self._running:
            try:
                # Ensure connection
                if self._state != ConnectionState.AUTHENTICATED:
                    if not await self._reconnect():
                        await asyncio.sleep(self.config.reconnect_delay_seconds)
                        continue
                
                # Start IDLE
                await self._set_state(ConnectionState.IDLE)
                
                idle_response = await self._client.idle_start(
                    timeout=self.config.idle_timeout_seconds
                )
                
                # Wait for IDLE response (new email or timeout)
                while self._running:
                    try:
                        msg = await asyncio.wait_for(
                            self._client.wait_server_push(),
                            timeout=self.config.idle_timeout_seconds
                        )
                        
                        # Check for EXISTS (new email) notification
                        for line in msg:
                            if isinstance(line, bytes):
                                line = line.decode()
                            if "EXISTS" in str(line):
                                await self._handle_new_email()
                                break
                        
                    except asyncio.TimeoutError:
                        # IDLE timeout - need to restart IDLE
                        break
                
                # Stop IDLE before reconnecting
                self._client.idle_done()
                
                # Wait for IDLE to complete
                await asyncio.wait_for(
                    self._client.wait_server_push(),
                    timeout=10
                )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"IDLE loop error: {e}")
                await self._set_state(ConnectionState.ERROR)
                await asyncio.sleep(self.config.reconnect_delay_seconds)
    
    async def _reconnect(self) -> bool:
        """Attempt to reconnect."""
        if self._reconnect_count >= self.config.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            return False
        
        self._reconnect_count += 1
        logger.info(f"Reconnection attempt {self._reconnect_count}/{self.config.max_reconnect_attempts}")
        
        # Close existing connection
        if self._client:
            try:
                await self._client.logout()
            except Exception:
                pass
            self._client = None
        
        # Reconnect
        if not await self.connect():
            return False
        
        if not await self.authenticate():
            return False
        
        if not await self.select_folder("INBOX"):
            return False
        
        return True
    
    async def _handle_new_email(self) -> None:
        """Handle new email notification."""
        if not self._client or not self.on_new_email:
            return
        
        try:
            # Search for new UIDs
            response = await self._client.search(f"UID {self._last_seen_uid + 1}:*")
            if response.result != "OK" or not response.lines:
                return
            
            uids_str = response.lines[0].decode().strip()
            if not uids_str:
                return
            
            new_uids = [int(uid) for uid in uids_str.split() if int(uid) > self._last_seen_uid]
            
            for uid in new_uids:
                notification = EmailNotification(
                    uid=uid,
                    folder="INBOX",
                    timestamp=datetime.utcnow(),
                )
                
                # Notify callback
                try:
                    result = self.on_new_email(notification)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"New email callback error: {e}")
                
                # Update last seen
                self._last_seen_uid = max(self._last_seen_uid, uid)
                
        except Exception as e:
            logger.error(f"Failed to handle new email: {e}")
    
    async def fetch_email(self, uid: int) -> Optional[dict]:
        """Fetch email by UID."""
        if not self._client:
            return None
        
        try:
            # Stop IDLE temporarily if active
            if self._state == ConnectionState.IDLE:
                self._client.idle_done()
                await asyncio.sleep(0.1)
            
            response = await self._client.fetch(str(uid), "(RFC822)")
            
            if response.result == "OK" and response.lines:
                # Parse email content
                for line in response.lines:
                    if isinstance(line, bytes) and b"RFC822" not in line:
                        return {"uid": uid, "raw": line}
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to fetch email {uid}: {e}")
            return None


class IMAPConnectionManager:
    """Manages multiple IMAP IDLE connections for tenants."""
    
    def __init__(self):
        self._connections: dict[str, IMAPIdleClient] = {}
        self._lock = asyncio.Lock()
    
    def _make_key(self, tenant_id: int, email_type: str) -> str:
        return f"{tenant_id}:{email_type}"
    
    async def start_connection(
        self,
        tenant_id: int,
        email_type: str,
        config: IMAPConfig,
        on_new_email: Callable[[EmailNotification], Any],
    ) -> bool:
        """Start IMAP IDLE connection for a tenant."""
        key = self._make_key(tenant_id, email_type)
        
        async with self._lock:
            # Stop existing connection if any
            if key in self._connections:
                await self._connections[key].stop_idle()
            
            # Create new client
            client = IMAPIdleClient(
                config=config,
                on_new_email=on_new_email,
                on_state_change=lambda state: logger.info(
                    f"IMAP [{tenant_id}:{email_type}] state: {state.value}"
                ),
            )
            
            # Connect and authenticate
            if not await client.connect():
                return False
            
            if not await client.authenticate():
                return False
            
            if not await client.select_folder("INBOX"):
                return False
            
            # Start IDLE
            await client.start_idle()
            
            self._connections[key] = client
            logger.info(f"Started IMAP IDLE for tenant {tenant_id} ({email_type})")
            return True
    
    async def stop_connection(self, tenant_id: int, email_type: str) -> None:
        """Stop IMAP IDLE connection."""
        key = self._make_key(tenant_id, email_type)
        
        async with self._lock:
            if key in self._connections:
                await self._connections[key].stop_idle()
                del self._connections[key]
                logger.info(f"Stopped IMAP IDLE for tenant {tenant_id} ({email_type})")
    
    async def stop_all(self) -> None:
        """Stop all IMAP connections."""
        async with self._lock:
            for key, client in list(self._connections.items()):
                await client.stop_idle()
            self._connections.clear()
            logger.info("Stopped all IMAP IDLE connections")
    
    def get_status(self, tenant_id: int, email_type: str) -> Optional[ConnectionState]:
        """Get connection status."""
        key = self._make_key(tenant_id, email_type)
        if key in self._connections:
            return self._connections[key].state
        return None
    
    def get_all_statuses(self) -> dict[str, str]:
        """Get all connection statuses."""
        return {
            key: client.state.value 
            for key, client in self._connections.items()
        }


# Global connection manager
_imap_manager: Optional[IMAPConnectionManager] = None


def get_imap_manager() -> IMAPConnectionManager:
    """Get global IMAP connection manager."""
    global _imap_manager
    if _imap_manager is None:
        _imap_manager = IMAPConnectionManager()
    return _imap_manager
