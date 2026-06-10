from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# from app.core.config
DATABASE_URL = ''

engine = create_engine(
    url=DATABASE_URL,
    pool_pre_ping=True    
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    db: Session = SessionLocal()
    try: 
        yield db
    finally: 
        db.close()