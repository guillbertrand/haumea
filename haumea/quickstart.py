import os
import re
import time
import logging
import argparse
import haumea
import shutil

def haumea_parse_args():
    parser = argparse.ArgumentParser(description='Haumea Static Site Generator',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("basedir", 
                        help="Directory name for your project ?")
    return parser.parse_args()

def main():
    FORMAT = '* %(levelname)s - %(message)s'
    logging.basicConfig(level=logging.INFO,format=FORMAT)
    logger = logging.getLogger('Haumea')
    logger.info('\U0001F680  Haumea %s - Quickstart \U0001F680' % haumea.__version__)
    args = haumea_parse_args()      
    if(args.basedir):
        # create project skeleton
        try:
            shutil.copytree('haumea/quickstart/',  args.basedir)
            logger.info('Create project folder "%s"' % args.basedir)
            logger.info('Create content folder "%s/content/"' % args.basedir)
            logger.info('Create content layouts "%s/layouts/"' % args.basedir)
            logger.info('Add sample files...')
            logger.info('\U0001F331  Yeah ! your project is ready \U0001F331');
            logger.info('Try to run the command "cd %s && haumea serve" to test it ! \U0001F30D' % args.basedir);
        except:
            logger.error('Unable to create haumea skeleton in "%s" directory' % args.basedir)

if __name__ == '__main__':
    main()
