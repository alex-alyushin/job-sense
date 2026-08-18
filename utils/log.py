import logging

def configure_logging(service_name: str):
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s [%(levelname)-4.4s] {service_name[:13]:>13} | %(message)s"
    )
