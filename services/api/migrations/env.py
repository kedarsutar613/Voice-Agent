from alembic import context
from app.database.session import Base, engine
from app.models import entities

with engine.connect() as connection:
    context.configure(
        connection=connection, target_metadata=Base.metadata, render_as_batch=True
    )
    with context.begin_transaction():
        context.run_migrations()
