"""
REST API Endpoints for Dashboard
"""

import json
import os
from quart import Blueprint, jsonify, request, session
from functools import wraps

api_bp = Blueprint('api', __name__)

# Config file paths
MODERATION_CONFIG = 'moderation_config.json'
LOGGING_CONFIG = 'logging_config.json'
TICKET_CONFIG = 'ticket_config.json'
WELCOME_CONFIG = 'welcome_channels.json'
STREAM_CONFIG = 'stream_config.json'


def require_guild_access(f):
    """Decorator to check if user has access to the guild"""
    @wraps(f)
    async def decorated_function(guild_id, *args, **kwargs):
        admin_guilds = session.get('admin_guilds', [])
        guild_ids = [g['id'] for g in admin_guilds]
        
        if guild_id not in guild_ids:
            return jsonify({'error': 'Нет доступа к этому серверу'}), 403
        
        return await f(guild_id, *args, **kwargs)
    return decorated_function


def load_json_config(filepath: str) -> dict:
    """Load JSON config file"""
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return {}


def save_json_config(filepath: str, data: dict):
    """Save JSON config file"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"Error saving {filepath}: {e}")
        return False


# ==================== Guild Info ====================

@api_bp.route('/guilds')
async def get_guilds():
    """Get list of user's admin guilds"""
    admin_guilds = session.get('admin_guilds', [])
    return jsonify(admin_guilds)


@api_bp.route('/guild/<guild_id>/info')
@require_guild_access
async def get_guild_info(guild_id):
    """Get detailed guild information"""
    from dashboard.app import get_bot
    bot = get_bot()
    
    if not bot:
        return jsonify({'error': 'Бот не подключен'}), 500
    
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({'error': 'Сервер не найден'}), 404
    
    return jsonify({
        'id': str(guild.id),
        'name': guild.name,
        'icon': str(guild.icon.url) if guild.icon else None,
        'member_count': guild.member_count,
        'owner_id': str(guild.owner_id),
        'created_at': guild.created_at.isoformat(),
    })


@api_bp.route('/guild/<guild_id>/channels')
@require_guild_access
async def get_guild_channels(guild_id):
    """Get guild channels"""
    from dashboard.app import get_bot
    bot = get_bot()
    
    if not bot:
        return jsonify({'error': 'Бот не подключен'}), 500
    
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({'error': 'Сервер не найден'}), 404
    
    channels = {
        'text': [],
        'voice': [],
        'category': []
    }
    
    for channel in guild.channels:
        channel_data = {
            'id': str(channel.id),
            'name': channel.name,
            'position': channel.position,
        }
        
        if hasattr(channel, 'category') and channel.category:
            channel_data['category_id'] = str(channel.category.id)
            channel_data['category_name'] = channel.category.name
        
        if channel.type.name == 'text':
            channels['text'].append(channel_data)
        elif channel.type.name == 'voice':
            channels['voice'].append(channel_data)
        elif channel.type.name == 'category':
            channels['category'].append(channel_data)
    
    return jsonify(channels)


@api_bp.route('/guild/<guild_id>/roles')
@require_guild_access
async def get_guild_roles(guild_id):
    """Get guild roles"""
    from dashboard.app import get_bot
    bot = get_bot()
    
    if not bot:
        return jsonify({'error': 'Бот не подключен'}), 500
    
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({'error': 'Сервер не найден'}), 404
    
    roles = []
    for role in guild.roles:
        if role.name != '@everyone':
            roles.append({
                'id': str(role.id),
                'name': role.name,
                'color': str(role.color),
                'position': role.position,
                'mentionable': role.mentionable,
            })
    
    # Sort by position (highest first)
    roles.sort(key=lambda r: r['position'], reverse=True)
    
    return jsonify(roles)


# ==================== Moderation Settings ====================

@api_bp.route('/guild/<guild_id>/moderation', methods=['GET'])
@require_guild_access
async def get_moderation_settings(guild_id):
    """Get moderation settings for guild"""
    config = load_json_config(MODERATION_CONFIG)
    guild_config = config.get(guild_id, {
        'log_channel_id': None,
        'allowed_domains': ['discord.gg', 'youtube.com', 'tenor.com', 'discord.com', 'youtu.be'],
        'blocked_domains': []
    })
    return jsonify(guild_config)


@api_bp.route('/guild/<guild_id>/moderation', methods=['POST'])
@require_guild_access
async def update_moderation_settings(guild_id):
    """Update moderation settings for guild"""
    data = await request.get_json()
    config = load_json_config(MODERATION_CONFIG)
    
    # Update guild config
    if guild_id not in config:
        config[guild_id] = {}
    
    if 'log_channel_id' in data:
        config[guild_id]['log_channel_id'] = data['log_channel_id']
    if 'allowed_domains' in data:
        config[guild_id]['allowed_domains'] = data['allowed_domains']
    if 'blocked_domains' in data:
        config[guild_id]['blocked_domains'] = data['blocked_domains']
    
    if save_json_config(MODERATION_CONFIG, config):
        # Reload config in the moderation cog if possible
        from dashboard.app import get_bot
        bot = get_bot()
        if bot:
            moder_cog = bot.get_cog('Moder')
            if moder_cog and hasattr(moder_cog, 'load_config'):
                moder_cog.load_config()
        
        return jsonify({'success': True, 'message': 'Настройки сохранены'})
    
    return jsonify({'error': 'Ошибка сохранения настроек'}), 500


# ==================== Logging Settings ====================

@api_bp.route('/guild/<guild_id>/logging', methods=['GET'])
@require_guild_access
async def get_logging_settings(guild_id):
    """Get logging settings for guild"""
    config = load_json_config(LOGGING_CONFIG)
    guild_config = config.get(guild_id, {
        'log_channel': None,
        'enabled_events': {
            'message_delete': True,
            'message_edit': True,
            'member_join': True,
            'member_leave': True,
            'member_ban': True,
            'member_unban': True,
            'member_update': True,
            'role_changes': True,
            'channel_changes': True,
            'voice_changes': True
        }
    })
    return jsonify(guild_config)


@api_bp.route('/guild/<guild_id>/logging', methods=['POST'])
@require_guild_access
async def update_logging_settings(guild_id):
    """Update logging settings for guild"""
    data = await request.get_json()
    config = load_json_config(LOGGING_CONFIG)
    
    if guild_id not in config:
        config[guild_id] = {'enabled_events': {}}
    
    if 'log_channel' in data:
        config[guild_id]['log_channel'] = data['log_channel']
    if 'enabled_events' in data:
        config[guild_id]['enabled_events'] = data['enabled_events']
    
    if save_json_config(LOGGING_CONFIG, config):
        from dashboard.app import get_bot
        bot = get_bot()
        if bot:
            logging_cog = bot.get_cog('Logging')
            if logging_cog and hasattr(logging_cog, 'load_config'):
                logging_cog.load_config()
        
        return jsonify({'success': True, 'message': 'Настройки логирования сохранены'})
    
    return jsonify({'error': 'Ошибка сохранения настроек'}), 500


# ==================== Tickets Settings ====================

@api_bp.route('/guild/<guild_id>/tickets', methods=['GET'])
@require_guild_access
async def get_tickets_settings(guild_id):
    """Get tickets settings for guild"""
    config = load_json_config(TICKET_CONFIG)
    
    # Default config structure
    default_config = {
        'bug': {'support_role_id': None, 'category_id': None},
        'idea': {'support_role_id': None, 'category_id': None},
        'complaint': {'support_role_id': None, 'category_id': None},
    }
    
    return jsonify(config if config else default_config)


@api_bp.route('/guild/<guild_id>/tickets', methods=['POST'])
@require_guild_access
async def update_tickets_settings(guild_id):
    """Update tickets settings"""
    data = await request.get_json()
    
    if save_json_config(TICKET_CONFIG, data):
        return jsonify({'success': True, 'message': 'Настройки тикетов сохранены'})
    
    return jsonify({'error': 'Ошибка сохранения настроек'}), 500


# ==================== Autorole Settings ====================

@api_bp.route('/guild/<guild_id>/autorole', methods=['GET'])
@require_guild_access
async def get_autorole_settings(guild_id):
    """Get autorole settings for guild"""
    welcome_config = load_json_config(WELCOME_CONFIG)
    
    # Get autorole ID from the cog (it's hardcoded currently)
    autorole_id = 1411068140024107031  # From autorole.py
    
    return jsonify({
        'autorole_id': str(autorole_id),
        'welcome_channel_id': welcome_config.get(guild_id) or welcome_config.get(int(guild_id))
    })


@api_bp.route('/guild/<guild_id>/autorole', methods=['POST'])
@require_guild_access
async def update_autorole_settings(guild_id):
    """Update autorole settings"""
    data = await request.get_json()
    welcome_config = load_json_config(WELCOME_CONFIG)
    
    if 'welcome_channel_id' in data:
        welcome_config[guild_id] = data['welcome_channel_id']
    
    if save_json_config(WELCOME_CONFIG, welcome_config):
        from dashboard.app import get_bot
        bot = get_bot()
        if bot:
            autorole_cog = bot.get_cog('AutoRole')
            if autorole_cog:
                autorole_cog.welcome_channels = autorole_cog.load_config()
        
        return jsonify({'success': True, 'message': 'Настройки авторолей сохранены'})
    
    return jsonify({'error': 'Ошибка сохранения настроек'}), 500


# ==================== TempVoice Settings ====================

@api_bp.route('/guild/<guild_id>/tempvoice', methods=['GET'])
@require_guild_access
async def get_tempvoice_settings(guild_id):
    """Get tempvoice settings for guild"""
    from dashboard.app import get_bot
    bot = get_bot()
    
    creator_channel_id = None
    active_channels = 0
    
    if bot:
        tempvoice_cog = bot.get_cog('TempVoiceCog')
        if tempvoice_cog:
            creator_channel_id = tempvoice_cog.voice_creators.get(int(guild_id))
            active_channels = len([c for c in tempvoice_cog.temp_channels.values() 
                                  if c.get('guild_id') == int(guild_id)])
    
    return jsonify({
        'creator_channel_id': str(creator_channel_id) if creator_channel_id else None,
        'active_channels': active_channels
    })


@api_bp.route('/guild/<guild_id>/tempvoice', methods=['POST'])
@require_guild_access
async def update_tempvoice_settings(guild_id):
    """Update tempvoice settings"""
    data = await request.get_json()
    
    from dashboard.app import get_bot
    bot = get_bot()
    
    if bot:
        tempvoice_cog = bot.get_cog('TempVoiceCog')
        if tempvoice_cog and 'creator_channel_id' in data:
            channel_id = data['creator_channel_id']
            if channel_id:
                tempvoice_cog.voice_creators[int(guild_id)] = int(channel_id)
            elif int(guild_id) in tempvoice_cog.voice_creators:
                del tempvoice_cog.voice_creators[int(guild_id)]
            
            return jsonify({'success': True, 'message': 'Настройки TempVoice сохранены'})
    
    return jsonify({'error': 'Ошибка сохранения настроек'}), 500


# ==================== Stream Notifications Settings ====================

@api_bp.route('/guild/<guild_id>/streams', methods=['GET'])
@require_guild_access
async def get_streams_settings(guild_id):
    """Get stream notification settings for guild"""
    config = load_json_config(STREAM_CONFIG)
    guild_config = config.get(guild_id, {
        'enabled': False,
        'channel_id': None,
        'ping_role_id': None,
        'embed_color': '#9146FF'
    })
    return jsonify(guild_config)


@api_bp.route('/guild/<guild_id>/streams', methods=['POST'])
@require_guild_access
async def update_streams_settings(guild_id):
    """Update stream notification settings"""
    data = await request.get_json()
    config = load_json_config(STREAM_CONFIG)
    
    if guild_id not in config:
        config[guild_id] = {}
    
    for key in ['enabled', 'channel_id', 'ping_role_id', 'embed_color']:
        if key in data:
            config[guild_id][key] = data[key]
    
    if save_json_config(STREAM_CONFIG, config):
        from dashboard.app import get_bot
        bot = get_bot()
        if bot:
            stream_cog = bot.get_cog('StreamNotifications')
            if stream_cog and hasattr(stream_cog, '_load_config'):
                stream_cog._load_config()
        
        return jsonify({'success': True, 'message': 'Настройки стримов сохранены'})
    
    return jsonify({'error': 'Ошибка сохранения настроек'}), 500


# ==================== Statistics ====================

@api_bp.route('/guild/<guild_id>/stats')
@require_guild_access
async def get_guild_stats(guild_id):
    """Get guild statistics"""
    from dashboard.app import get_bot
    bot = get_bot()
    
    if not bot:
        return jsonify({'error': 'Бот не подключен'}), 500
    
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({'error': 'Сервер не найден'}), 404
    
    # Count channels by type
    text_channels = len([c for c in guild.channels if c.type.name == 'text'])
    voice_channels = len([c for c in guild.channels if c.type.name == 'voice'])
    
    # Count online members
    online_members = len([m for m in guild.members if m.status.name != 'offline'])
    
    return jsonify({
        'member_count': guild.member_count,
        'online_count': online_members,
        'text_channels': text_channels,
        'voice_channels': voice_channels,
        'role_count': len(guild.roles),
        'emoji_count': len(guild.emojis),
        'boost_level': guild.premium_tier,
        'boost_count': guild.premium_subscription_count,
    })
