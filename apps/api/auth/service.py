"""Authentication service with database operations."""

import re
from typing import Optional
import asyncpg

from .password import hash_password, verify_password
from .jwt import create_access_token
from .models import UserResponse, AuthResponse, TokenResponse


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text


class AuthService:
    """Authentication service."""
    
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
    
    async def register(
        self,
        email: str,
        password: str,
        company_name: str,
        name: Optional[str] = None,
    ) -> AuthResponse:
        """
        Register new user and tenant.
        
        Creates:
        1. New tenant with company_name
        2. New user as admin of that tenant
        
        Returns:
            AuthResponse with user info and token
        """
        async with self.pool.acquire() as conn:
            # Check if email exists
            existing = await conn.fetchval(
                "SELECT id FROM users WHERE email = $1",
                email.lower(),
            )
            if existing:
                raise ValueError("Email already registered")
            
            # Create tenant
            slug = slugify(company_name)
            
            # Ensure unique slug
            base_slug = slug
            counter = 1
            while True:
                existing_slug = await conn.fetchval(
                    "SELECT id FROM tenants WHERE slug = $1",
                    slug,
                )
                if not existing_slug:
                    break
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            tenant_row = await conn.fetchrow(
                """
                INSERT INTO tenants (name, slug)
                VALUES ($1, $2)
                RETURNING id, name, slug
                """,
                company_name,
                slug,
            )
            tenant_id = tenant_row["id"]
            
            # Create user
            password_hash = hash_password(password)
            user_row = await conn.fetchrow(
                """
                INSERT INTO users (tenant_id, email, password_hash, name, role, is_active, email_verified)
                VALUES ($1, $2, $3, $4, 'admin', true, false)
                RETURNING id, email, name, role
                """,
                tenant_id,
                email.lower(),
                password_hash,
                name or company_name,
            )
            
            # Create JWT token
            token, jti, expires_at = create_access_token(
                user_id=user_row["id"],
                tenant_id=tenant_id,
                email=user_row["email"],
                role=user_row["role"],
            )
            
            # Store session
            await conn.execute(
                """
                INSERT INTO sessions (user_id, token_jti, expires_at)
                VALUES ($1, $2, $3)
                """,
                user_row["id"],
                jti,
                expires_at,
            )
            
            return AuthResponse(
                user=UserResponse(
                    id=user_row["id"],
                    email=user_row["email"],
                    name=user_row["name"],
                    role=user_row["role"],
                    tenant_id=tenant_id,
                    tenant_name=tenant_row["name"],
                    tenant_slug=tenant_row["slug"],
                ),
                token=TokenResponse(
                    access_token=token,
                    expires_at=expires_at,
                ),
            )
    
    async def login(self, email: str, password: str) -> AuthResponse:
        """
        Login user.
        
        Returns:
            AuthResponse with user info and token
        """
        async with self.pool.acquire() as conn:
            # Get user with tenant
            row = await conn.fetchrow(
                """
                SELECT 
                    u.id, u.email, u.password_hash, u.name, u.role, u.is_active,
                    t.id as tenant_id, t.name as tenant_name, t.slug as tenant_slug, t.is_active as tenant_active
                FROM users u
                JOIN tenants t ON u.tenant_id = t.id
                WHERE u.email = $1
                """,
                email.lower(),
            )
            
            if not row:
                raise ValueError("Invalid email or password")
            
            if not row["is_active"]:
                raise ValueError("Account is disabled")
            
            if not row["tenant_active"]:
                raise ValueError("Organization is disabled")
            
            if not verify_password(password, row["password_hash"]):
                raise ValueError("Invalid email or password")
            
            # Create JWT token
            token, jti, expires_at = create_access_token(
                user_id=row["id"],
                tenant_id=row["tenant_id"],
                email=row["email"],
                role=row["role"],
            )
            
            # Store session
            await conn.execute(
                """
                INSERT INTO sessions (user_id, token_jti, expires_at)
                VALUES ($1, $2, $3)
                """,
                row["id"],
                jti,
                expires_at,
            )
            
            # Update last login
            await conn.execute(
                "UPDATE users SET last_login_at = NOW() WHERE id = $1",
                row["id"],
            )
            
            return AuthResponse(
                user=UserResponse(
                    id=row["id"],
                    email=row["email"],
                    name=row["name"],
                    role=row["role"],
                    tenant_id=row["tenant_id"],
                    tenant_name=row["tenant_name"],
                    tenant_slug=row["tenant_slug"],
                ),
                token=TokenResponse(
                    access_token=token,
                    expires_at=expires_at,
                ),
            )
    
    async def logout(self, jti: str) -> bool:
        """
        Logout by invalidating session.
        
        Returns:
            True if session was invalidated
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM sessions WHERE token_jti = $1",
                jti,
            )
            return "DELETE 1" in result
    
    async def get_user_by_id(self, user_id: int) -> Optional[UserResponse]:
        """Get user by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 
                    u.id, u.email, u.name, u.role,
                    t.id as tenant_id, t.name as tenant_name, t.slug as tenant_slug
                FROM users u
                JOIN tenants t ON u.tenant_id = t.id
                WHERE u.id = $1 AND u.is_active = true AND t.is_active = true
                """,
                user_id,
            )
            
            if not row:
                return None
            
            return UserResponse(
                id=row["id"],
                email=row["email"],
                name=row["name"],
                role=row["role"],
                tenant_id=row["tenant_id"],
                tenant_name=row["tenant_name"],
                tenant_slug=row["tenant_slug"],
            )
    
    async def is_session_valid(self, jti: str) -> bool:
        """Check if session is still valid."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM sessions WHERE token_jti = $1 AND expires_at > NOW()",
                jti,
            )
            return row is not None
