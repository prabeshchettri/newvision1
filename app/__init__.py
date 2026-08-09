import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
from flask_migrate import Migrate
from app.config import config
from app.models import db, User

login_manager = LoginManager()
csrf = CSRFProtect()
mail = Mail()
migrate = Migrate()

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__, instance_relative_config=True)
    if os.environ.get('VERCEL') or os.environ.get('VERCEL_ENV'):
        app.instance_path = '/tmp/nva_instance'
        try:
            os.makedirs(app.instance_path, exist_ok=True)
        except OSError:
            pass
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    app.config.from_object(config.get(config_name, config['default']))
    # Multi-path templates/static for Vercel + local
    from jinja2 import FileSystemLoader, ChoiceLoader
    _app_dir = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.abspath(os.path.join(_app_dir, '..'))
    # Also search /var/task (Vercel function root)
    _task = os.environ.get('LAMBDA_TASK_ROOT') or '/var/task'
    _candidates = [
        os.path.join(_app_dir, 'templates'),
        os.path.join(_root, 'app', 'templates'),
        os.path.join(_root, 'templates'),
        os.path.join(_root, 'api', 'templates'),
        os.path.join(_task, 'app', 'templates'),
        os.path.join(_task, 'templates'),
        os.path.join(_task, 'api', 'templates'),
        os.path.join(_task, 'api', '..', 'app', 'templates'),
        os.path.join(_task, 'api', '..', 'templates'),
    ]
    _paths = []
    for _p in _candidates:
        _p = os.path.abspath(_p)
        if os.path.isdir(_p) and _p not in _paths:
            _paths.append(_p)
    if _paths:
        app.jinja_loader = FileSystemLoader(_paths)
        app.template_folder = _paths[0]
    else:
        # last resort: default relative to package
        app.template_folder = 'templates'
        print('NVA WARNING: no template dirs found')
        try:
            print('NVA listdir app_dir', os.listdir(_app_dir)[:30])
            print('NVA listdir root', os.listdir(_root)[:30])
            if os.path.isdir(_task):
                print('NVA listdir task', os.listdir(_task)[:40])
        except Exception as e:
            print('NVA listdir err', e)
    for _p in [
        os.path.join(_app_dir, 'static'),
        os.path.join(_root, 'static'),
        os.path.join(_root, 'app', 'static'),
        os.path.join(_task, 'static'),
        os.path.join(_task, 'app', 'static'),
    ]:
        _p = os.path.abspath(_p)
        if os.path.isdir(_p):
            app.static_folder = _p
            app.static_url_path = '/static'
            break
    print('NVA template paths', _paths)
    if not _paths:
        # Walk /var/task to find any templates dir (Vercel packaging)
        _search_roots = [_task, _root, _app_dir]
        for _sr in _search_roots:
            if not os.path.isdir(_sr):
                continue
            for _dirpath, _dirnames, _filenames in os.walk(_sr):
                if _dirpath.endswith(os.path.join('public', 'pages')) and 'home.html' in _filenames:
                    # parent of public/pages = templates root? structure is templates/public/pages
                    # or app/templates/public/pages
                    _tpl_root = os.path.dirname(os.path.dirname(_dirpath))  # .../templates
                    if os.path.isdir(_tpl_root) and _tpl_root not in _paths:
                        _paths.append(_tpl_root)
                        print('NVA found templates via walk:', _tpl_root)
                # limit walk depth cost
                if _dirpath.count(os.sep) - _sr.count(os.sep) > 6:
                    _dirnames[:] = []
        if _paths:
            app.jinja_loader = FileSystemLoader(_paths)
            app.template_folder = _paths[0]

    print('NVA static', getattr(app, 'static_folder', None))
    # Force: if still empty, try every possible location (must be in includeFiles)
    if not _paths:
        for _forced in [
            os.path.join(_app_dir, 'templates'),
            os.path.join(_root, 'templates'),
            os.path.join(_root, 'api', 'templates'),
            os.path.join(_task, 'templates'),
            os.path.join(_task, 'app', 'templates'),
            os.path.join(_task, 'api', 'templates'),
        ]:
            _forced = os.path.abspath(_forced)
            print('NVA force try', _forced, 'exists', os.path.isdir(_forced))
            if os.path.isdir(_forced):
                from jinja2 import FileSystemLoader as _FSL
                app.jinja_loader = _FSL([_forced])
                app.template_folder = _forced
                _paths = [_forced]
                break
        if not _paths:
            print('NVA CRITICAL: no templates found anywhere')
            try:
                print('NVA /var/task listing:', os.listdir(_task)[:50] if os.path.isdir(_task) else 'no task')
            except Exception as e:
                print('NVA list err', e)


    
    # Ensure folders (on Vercel only /tmp is writable)
    def _safe_mkdir(path):
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            print('mkdir skip:', path, e)

    _safe_mkdir(app.instance_path)
    _safe_mkdir(app.config['UPLOAD_FOLDER'])
    _safe_mkdir(app.config.get('BACKUP_FOLDER', os.path.join(app.instance_path, 'backups')))
    _safe_mkdir(app.config.get('LOG_FOLDER', os.path.join(app.instance_path, 'logs')))
    for sub in ['slider', 'gallery', 'staff', 'news', 'blogs', 'facilities', 'logos', 'notices', 'downloads', 'settings', 'general']:
        _safe_mkdir(os.path.join(app.config['UPLOAD_FOLDER'], sub))
    
    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    print(f"MAIL configured: server={app.config.get('MAIL_SERVER')} user={app.config.get('MAIL_USERNAME')}")
    migrate.init_app(app, db)
    
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'warning'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Register blueprints
    from app.blueprints.public_routes import public_bp
    from app.blueprints.admin_routes import admin_bp
    from app.blueprints.auth_routes import auth_bp
    
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(auth_bp, url_prefix='/auth')

    @app.route('/api/health')
    @app.route('/health')
    def vercel_health():
        return {'ok': True, 'service': 'new-vision-academy'}, 200

    @app.before_request
    def _log_path():
        try:
            from flask import request
            if os.environ.get('VERCEL'):
                print('NVA PATH', request.path, 'URL', request.url)
        except Exception:
            pass

    
    @app.template_filter('media')
    def media_filter(path):
        try:
            from app.utils.helpers import media_url
            return media_url(path) or ''
        except Exception:
            if not path:
                return ''
            path = str(path)
            if path.startswith('http'):
                return path
            return '/uploads/' + path.lstrip('/')

    # Context processors
    @app.context_processor
    def inject_globals():
        from app.models import SchoolSetting, Notice
        settings = {}
        try:
            for s in SchoolSetting.query.all():
                settings[s.key] = s.value
        except:
            pass
        latest_notices = []
        try:
            latest_notices = Notice.query.filter_by(is_active=True).order_by(Notice.is_pinned.desc(), Notice.publish_date.desc()).limit(5).all()
        except:
            pass
        return {
            'school_settings': settings,
            'latest_notices_ticker': latest_notices,
            'school_name': settings.get('school_name', 'New Vision Academy'),
            'school_phone': settings.get('phone', '+977-9841333476'),
            'school_email': settings.get('display_email') or settings.get('email', 'info@newvisionacademy.edu.np'),
            'smtp_email': settings.get('email', 'argonbhujel1@gmail.com'),
            'school_address': settings.get('address', 'Urlabari-8, Morang, Koshi Province, Nepal'),
            'whatsapp_number': settings.get('whatsapp', '9779841333476'),
            'school_lat': settings.get('latitude', '26.64513162062879'),
            'school_lng': settings.get('longitude', '87.63686430000001'),
        }
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        try:
            return render_template('public/pages/404.html'), 404
        except Exception:
            return '<h1>404 Not Found</h1>', 404
    
    @app.errorhandler(500)
    def server_error(e):
        import traceback
        print('=== 500 ERROR ===')
        traceback.print_exc()
        from flask import render_template
        try:
            return render_template('public/pages/500.html'), 500
        except Exception:
            return '<h1>500 Server Error</h1>', 500
    
    # Create tables and seed
    with app.app_context():
        db.create_all()
        from app.utils.seed import seed_database
        seed_database()
    
    # AI Auto-Reply:
    # - Local/Render: background thread
    # - Vercel serverless: no long-lived threads; process on each request (lightweight)
    try:
        if os.environ.get('VERCEL') or os.environ.get('VERCEL_ENV'):
            @app.before_request
            def _vercel_ai_tick():
                try:
                    from flask import request
                    # Skip static-ish paths to reduce load
                    if request.path.startswith('/static') or request.path.startswith('/uploads'):
                        return
                    from app.services.ai_reply import process_pending_replies
                    process_pending_replies()
                except Exception as e:
                    print('Vercel AI tick:', e)
            print('AI: Vercel before_request mode')
        else:
            from app.services.ai_reply import start_ai_scheduler
            start_ai_scheduler(app)
    except Exception as e:
        print(f"AI scheduler note: {e}")
    
    return app
