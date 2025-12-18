"""
Discord OAuth2 Authentication Routes
"""

import os
import aiohttp
from quart import Blueprint, redirect, request, session, url_for, current_app
from urllib.parse import urlencode

auth_bp = Blueprint('auth', __name__)

# OAuth2 scopes
OAUTH2_SCOPES = ['identify', 'guilds']


def get_oauth2_url():
    """Generate Discord OAuth2 authorization URL"""
    params = {
        'client_id': current_app.config['DISCORD_CLIENT_ID'],
        'redirect_uri': current_app.config['DISCORD_REDIRECT_URI'],
        'response_type': 'code',
        'scope': ' '.join(OAUTH2_SCOPES),
    }
    return f"https://discord.com/api/oauth2/authorize?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    """Exchange authorization code for access token"""
    data = {
        'client_id': current_app.config['DISCORD_CLIENT_ID'],
        'client_secret': current_app.config['DISCORD_CLIENT_SECRET'],
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': current_app.config['DISCORD_REDIRECT_URI'],
    }
    
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    async with aiohttp.ClientSession() as session_http:
        async with session_http.post(
            'https://discord.com/api/oauth2/token',
            data=data,
            headers=headers
        ) as response:
            return await response.json()


async def get_user_info(access_token: str) -> dict:
    """Get user information from Discord API"""
    headers = {'Authorization': f'Bearer {access_token}'}
    
    async with aiohttp.ClientSession() as session_http:
        async with session_http.get(
            f"{current_app.config['DISCORD_API_BASE']}/users/@me",
            headers=headers
        ) as response:
            return await response.json()


async def get_user_guilds(access_token: str) -> list:
    """Get user's guilds from Discord API"""
    headers = {'Authorization': f'Bearer {access_token}'}
    
    async with aiohttp.ClientSession() as session_http:
        async with session_http.get(
            f"{current_app.config['DISCORD_API_BASE']}/users/@me/guilds",
            headers=headers
        ) as response:
            return await response.json()


def filter_admin_guilds(guilds: list, bot_guild_ids: list) -> list:
    """Filter guilds where user is admin and bot is present"""
    admin_guilds = []
    
    for guild in guilds:
        # Check if user has Administrator permission (0x8)
        permissions = int(guild.get('permissions', 0))
        is_admin = (permissions & 0x8) == 0x8 or guild.get('owner', False)
        
        # Check if bot is in this guild
        bot_present = guild['id'] in bot_guild_ids
        
        if is_admin and bot_present:
            admin_guilds.append({
                'id': guild['id'],
                'name': guild['name'],
                'icon': guild.get('icon'),
                'owner': guild.get('owner', False),
            })
    
    return admin_guilds


@auth_bp.route('/login')
async def login():
    """Redirect to Discord OAuth2 authorization"""
    return redirect(get_oauth2_url())


@auth_bp.route('/callback')
async def callback():
    """Handle OAuth2 callback from Discord"""
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        return redirect(url_for('views.index', error='auth_denied'))
    
    if not code:
        return redirect(url_for('views.index', error='no_code'))
    
    # Exchange code for token
    token_data = await exchange_code(code)
    
    if 'access_token' not in token_data:
        return redirect(url_for('views.index', error='token_error'))
    
    access_token = token_data['access_token']
    
    # Get user info
    user_info = await get_user_info(access_token)
    
    if 'id' not in user_info:
        return redirect(url_for('views.index', error='user_error'))
    
    # Get user's guilds
    user_guilds = await get_user_guilds(access_token)
    
    # Get bot's guild IDs
    from dashboard.app import get_bot
    bot = get_bot()
    bot_guild_ids = [str(g.id) for g in bot.guilds] if bot else []
    
    # Filter admin guilds where bot is present
    admin_guilds = filter_admin_guilds(user_guilds, bot_guild_ids)
    
    # Store in session
    session['user'] = {
        'id': user_info['id'],
        'username': user_info['username'],
        'discriminator': user_info.get('discriminator', '0'),
        'avatar': user_info.get('avatar'),
        'global_name': user_info.get('global_name'),
    }
    session['access_token'] = access_token
    session['admin_guilds'] = admin_guilds
    
    return redirect(url_for('views.dashboard'))


@auth_bp.route('/logout')
async def logout():
    """Clear session and logout"""
    session.clear()
    return redirect(url_for('views.index'))
