from db.models import create_tables
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("init_tables")

if __name__ == "__main__":
    logger.info("Creando tablas en la base de datos...")
    create_tables()
    logger.info("Proceso finalizado.")
