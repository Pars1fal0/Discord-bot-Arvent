"""
View Routes - HTML Pages
"""

from quart import Blueprint, render_template, session, redirect, url_for

views_bp = Blueprint('views', __name__)


@views_bp.route('/')
async def index():
    """Landing page / Login page"""
    if 'user' in session:
        return redirect(url_for('views.dashboard'))
    return await render_template('login.html')


@views_bp.route('/dashboard')
async def dashboard():
    """Main dashboard - server selection"""
    if 'user' not in session:
        return redirect(url_for('views.index'))
    
    admin_guilds = session.get('admin_guilds', [])
    return await render_template('dashboard.html', guilds=admin_guilds)


@views_bp.route('/server/<guild_id>')
async def server_dashboard(guild_id):
    """Server-specific dashboard"""
    if 'user' not in session:
        return redirect(url_for('views.index'))
    
    # Check access
    admin_guilds = session.get('admin_guilds', [])
    guild_ids = [g['id'] for g in admin_guilds]
    
    if guild_id not in guild_ids:
        return redirect(url_for('views.dashboard'))
    
    # Find guild info
    guild = next((g for g in admin_guilds if g['id'] == guild_id), None)
    
    return await render_template('server.html', guild=guild, guild_id=guild_id)


@views_bp.route('/server/<guild_id>/moderation')
async def moderation_page(guild_id):
    """Moderation settings page"""
    if 'user' not in session:
        return redirect(url_for('views.index'))
    
    admin_guilds = session.get('admin_guilds', [])
    guild_ids = [g['id'] for g in admin_guilds]
    
    if guild_id not in guild_ids:
        return redirect(url_for('views.dashboard'))
    
    guild = next((g for g in admin_guilds if g['id'] == guild_id), None)
    return await render_template('moderation.html', guild=guild, guild_id=guild_id)


@views_bp.route('/server/<guild_id>/logging')
async def logging_page(guild_id):
    """Logging settings page"""
    if 'user' not in session:
        return redirect(url_for('views.index'))
    
    admin_guilds = session.get('admin_guilds', [])
    guild_ids = [g['id'] for g in admin_guilds]
    
    if guild_id not in guild_ids:
        return redirect(url_for('views.dashboard'))
    
    guild = next((g for g in admin_guilds if g['id'] == guild_id), None)
    return await render_template('logging.html', guild=guild, guild_id=guild_id)


@views_bp.route('/server/<guild_id>/tickets')
async def tickets_page(guild_id):
    """Tickets settings page"""
    if 'user' not in session:
        return redirect(url_for('views.index'))
    
    admin_guilds = session.get('admin_guilds', [])
    guild_ids = [g['id'] for g in admin_guilds]
    
    if guild_id not in guild_ids:
        return redirect(url_for('views.dashboard'))
    
    guild = next((g for g in admin_guilds if g['id'] == guild_id), None)
    return await render_template('tickets.html', guild=guild, guild_id=guild_id)


@views_bp.route('/server/<guild_id>/autorole')
async def autorole_page(guild_id):
    """Autorole settings page"""
    if 'user' not in session:
        return redirect(url_for('views.index'))
    
    admin_guilds = session.get('admin_guilds', [])
    guild_ids = [g['id'] for g in admin_guilds]
    
    if guild_id not in guild_ids:
        return redirect(url_for('views.dashboard'))
    
    guild = next((g for g in admin_guilds if g['id'] == guild_id), None)
    return await render_template('autorole.html', guild=guild, guild_id=guild_id)


@views_bp.route('/server/<guild_id>/tempvoice')
async def tempvoice_page(guild_id):
    """TempVoice settings page"""
    if 'user' not in session:
        return redirect(url_for('views.index'))
    
    admin_guilds = session.get('admin_guilds', [])
    guild_ids = [g['id'] for g in admin_guilds]
    
    if guild_id not in guild_ids:
        return redirect(url_for('views.dashboard'))
    
    guild = next((g for g in admin_guilds if g['id'] == guild_id), None)
    return await render_template('tempvoice.html', guild=guild, guild_id=guild_id)


@views_bp.route('/server/<guild_id>/streams')
async def streams_page(guild_id):
    """Stream notifications settings page"""
    if 'user' not in session:
        return redirect(url_for('views.index'))
    
    admin_guilds = session.get('admin_guilds', [])
    guild_ids = [g['id'] for g in admin_guilds]
    
    if guild_id not in guild_ids:
        return redirect(url_for('views.dashboard'))
    
    guild = next((g for g in admin_guilds if g['id'] == guild_id), None)
    return await render_template('streams.html', guild=guild, guild_id=guild_id)
