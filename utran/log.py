import sys
from loguru import logger

__all__ = ['logger']

logger.level("WARNING")  # DEBUG、INFO、WARNING、ERROR、CRITICAL
# logger.add(sys.stdout, level="WARNING")
# logger.add("file_{time}.log", rotation="500 MB", level="WARNING")

if __name__ == '__main__':    
    logger.debug('This is a debug message')
    logger.info('This is an info message')
    logger.warning('This is a warning message')
    logger.error('This is an error message')
    logger.critical('This is a critical message')
    logger.success("ok")