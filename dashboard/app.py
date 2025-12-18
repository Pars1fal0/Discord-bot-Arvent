"""
Discord Bot Dashboard - Main Application
Quart-based web dashboard for Discord bot configuration
"""

import os
import asyncio
from quart import Quart, session, redirect, url_for, render_template
from quart_cors import cors
import secrets

# Bot instance will be set when creating the app
bot_instance = None


def create_app(bot=None):
    """Create and configure the Quart application"""
    global bot_instance
    bot_instance = bot
    
    app = Quart(__name__, 
                template_folder='templates',
                static_folder='static')
    
    # Configuration
    app.secret_key = os.getenv('DASHBOARD_SECRET_KEY', secrets.token_hex(32))
    app.config['SESSION_COOKIE_SECURE'] = False  # Set True in production with HTTPS
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    # Discord OAuth2 configuration
    app.config['DISCORD_CLIENT_ID'] = os.getenv('DISCORD_CLIENT_ID')
    app.config['DISCORD_CLIENT_SECRET'] = os.getenv('DISCORD_CLIENT_SECRET')
    app.config['DISCORD_REDIRECT_URI'] = os.getenv('DASHBOARD_HOST', 'http://localhost:5000') + '/auth/callback'
    app.config['DISCORD_API_BASE'] = 'https://discord.com/api/v10'
    
    # Enable CORS
    app = cors(app, allow_origin="*")
    
    # Register blueprints
    from dashboard.routes.auth import auth_bp
    from dashboard.routes.api import api_bp
    from dashboard.routes.views import views_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(views_bp)
    
    @app.route('/health')
    async def health_check():
        """Health check endpoint"""
        return {'status': 'ok', 'bot_connected': bot_instance is not None}
    
    @app.before_request
    async def before_request():
        """Check if user is authenticated for protected routes"""
        from quart import request
        
        # Public routes that don't require authentication
        public_routes = ['auth.login', 'auth.callback', 'auth.logout', 'health_check', 
                        'views.index', 'static']
        
        if request.endpoint and any(request.endpoint.startswith(r) for r in public_routes):
            return None
        
        # Check if user is authenticated
        if 'user' not in session:
            return redirect(url_for('views.index'))
    
    @app.context_processor
    def inject_globals():
        """Inject global variables into templates"""
        return {
            'bot': bot_instance,
            'user': session.get('user'),
        }
    
    return app


def get_bot():
    """Get the bot instance"""
    return bot_instance
