import os
import logging
import argparse
import haumea
import pysftp
import json

_QUICKSTART_PATH = os.path.join(
    os.path.dirname(
        os.path.abspath(haumea.__file__)
    ),
    'deploy'
)


def haumea_parse_args():
    parser = argparse.ArgumentParser(
        description='Haumea Static Site Generator',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-e", "--env",
                        default="test",
                        help="")
    return parser.parse_args()


def get_config():
    conf = {}
    filename = 'config.json'
    if os.path.exists(filename):
        with open(filename) as json_file:
            conf = json.load(json_file)
    return conf
    

def main():
    FORMAT = '* %(levelname)s - %(message)s'
    logging.basicConfig(level=logging.INFO, format=FORMAT)
    logger = logging.getLogger('Haumea')
    logger.info(
        '\U0001F680  Haumea %s - Deploy \U0001F680' %
        haumea.__version__)
    args = haumea_parse_args()
    
    deploy_param = {}
    conf = get_config()
    if "deploy" in conf:
        for p in conf["deploy"]:
            if p['env'] == args.env:
                deploy_param = p
                break

    if deploy_param:
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None   
        with pysftp.Connection(host=deploy_param['host'], username=deploy_param['username'], password=deploy_param['password'], cnopts=cnopts) as sftp:
            print("Connection succesfully stablished ... ")
            sftp.put_r('public', deploy_param['remote_path'], preserve_mtime=True)


if __name__ == '__main__':
    main()
