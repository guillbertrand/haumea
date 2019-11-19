import os
import logging
import argparse
import haumea
import shutil

_QUICKSTART_PATH = os.path.join(
    os.path.dirname(
        os.path.abspath(haumea.__file__)
    ),
    'quickstart'
)


def haumea_parse_args():
    parser = argparse.ArgumentParser(
        description='Haumea Static Site Generator',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("yourprojectname",
                        help="What's your project name ?")
    return parser.parse_args()


def main():
    FORMAT = '* %(levelname)s - %(message)s'
    logging.basicConfig(level=logging.INFO, format=FORMAT)
    logger = logging.getLogger('Haumea')
    logger.info(
        '\U0001F680  Haumea %s - Quickstart \U0001F680' %
        haumea.__version__)
    args = haumea_parse_args()
    if(args.yourprojectname):
        # create project skeleton
        try:
            shutil.copytree(_QUICKSTART_PATH, args.yourprojectname)
            logger.info('Create project folder "%s"' % args.yourprojectname)
            logger.info(
                'Create content folder "%s/content/"' %
                args.yourprojectname)
            logger.info(
                'Create content layouts "%s/layouts/"' %
                args.yourprojectname)
            logger.info(
                'Create content layouts "%s/static/"' %
                args.yourprojectname)
            logger.info('Add sample files...')
            logger.info('\U0001F331  Yeah ! your project is ready \U0001F331')
            logger.info(
                'Try to run the command "cd %s && haumea serve" to test it !'
                '\U0001F30D' % args.yourprojectname)
        except BaseException:
            logger.error(
                'Unable to create haumea skeleton in "%s" directory' %
                args.yourprojectname)


if __name__ == '__main__':
    main()
