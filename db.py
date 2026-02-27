from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
import datetime
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

print("Creando base de datos...")

engine = create_engine("sqlite:///database.db")

Base = declarative_base()
class Tienda(Base):
    __tablename__ = "tiendas"

    id = Column(Integer, primary_key=True)
    nombre = Column(String, unique=True, nullable=False)

    dispositivos = relationship("Dispositivo", back_populates="tienda_rel")

Session = sessionmaker(bind=engine)


class Dispositivo(Base):
    __tablename__ = "dispositivos"

    id = Column(Integer, primary_key=True)
    nombre = Column(String, nullable=False)
    ip = Column(String, nullable=False)
    tipo = Column(String, nullable=False)
    tienda = Column(String, nullable=False)



class Historial(Base):

    __tablename__ = "historial"

    id = Column(Integer, primary_key=True)

    dispositivo = Column(String)

    estado = Column(String)

    fecha = Column(DateTime, default=datetime.datetime.now)


Base.metadata.create_all(engine)

print("Base de datos creada correctamente")