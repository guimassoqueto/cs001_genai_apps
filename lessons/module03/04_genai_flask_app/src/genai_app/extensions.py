from flask_caching import Cache

# Created unbound and attached to the app in create_app(), so every app (and every test) gets its own.
cache = Cache()
