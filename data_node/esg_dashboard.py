import os
import pwd
import grp
import stat
import logging
import zipfile
import requests
import yaml
from git import Repo
from clint.textui import progress
from esgf_utilities import esg_functions
from esgf_utilities import pybash
from plumbum.commands import ProcessExecutionError

logger = logging.getLogger("esgf_logger" +"."+ __name__)

with open(os.path.join(os.path.dirname(__file__), os.pardir, 'esg_config.yaml'), 'r') as config_file:
    config = yaml.load(config_file)

def download_extract(url, dest_dir, owner_user, owner_group):
    r = requests.get(url)
    remote_file = url.rsplit("/")[1]
    filename = os.path.join(os.sep, "tmp", remote_file)
    with open(filename, "wb") as localfile:
        total_length = int(r.headers.get('content-length'))
        for chunk in progress.bar(r.iter_content(chunk_size=1024), expected_size=(total_length/1024) + 1):
            if chunk:
                localfile.write(chunk)
                localfile.flush()

    pybash.mkdir_p(dest_dir)
    with zipfile.ZipFile(localfile) as archive:
        archive.extractall(dest_dir)

    uid = esg_functions.get_user_id(user)
    gid = esg_functions.get_group_id(group)
    esg_functions.change_ownership_recursive(dest_dir, uid, gid)

def setup_dashboard():

    if os.path.isdir("/usr/local/tomcat/webapps/esgf-stats-api"):
        stats_api_install = raw_input("Existing Stats API installation found.  Do you want to continue with the Stats API installation [y/N]: " ) or "no"
        if stats_api_install.lower() in ["no", "n"]:
            return
    print "\n*******************************"
    print "Setting up ESGF Stats API (dashboard)"
    print "******************************* \n"

    tomcat_webapps = os.path.join(os.sep, "usr", "local", "tomcat", "webapps")


    stats_api_url = os.path.join("http://", config["esgf_dist_mirror"], "dist", "devel", "esgf-stats-api", "esgf-stats-api.war")
    dest_dir = os.path.join(tomcat_webapps, "esgf-stats-api")
    download_extract(stats_api_url, dest_dir, "tomcat", "tomcat")

    # execute dashboard installation script (without the postgres schema)
    run_dashboard_script()

    # create non-privileged user to run the dashboard application
    esg_functions.add_unix_group("dashboard")
    useradd_options = ["-s", "/sbin/nologin", "-g", "dashboard", "-d", "/usr/local/dashboard", "dashboard"]
    try:
        esg_functions.call_binary("useradd", useradd_options)
    except ProcessExecutionError, err:
        if err.retcode == 9:
            pass
        else:
            raise
    DASHBOARD_USER_ID = pwd.getpwnam("dashboard").pw_uid
    DASHBOARD_GROUP_ID = grp.getgrnam("dashboard").gr_gid
    esg_functions.change_ownership_recursive("/usr/local/esgf-dashboard-ip", DASHBOARD_USER_ID, DASHBOARD_GROUP_ID)
    os.chmod("/var/run", stat.S_IWRITE)
    os.chmod("/var/run", stat.S_IWGRP)
    os.chmod("/var/run", stat.S_IWOTH)

    start_dashboard_service()

def start_dashboard_service():
    os.chmod("/usr/local/esgf-dashboard-ip/bin/ip.service", 0555)
    esg_functions.stream_subprocess_output("/usr/local/esgf-dashboard-ip/bin/ip.service start")


def clone_dashboard_repo():
    ''' Clone esgf-dashboard repo from Github'''
    if os.path.isdir("/usr/local/esgf-dashboard"):
        print "esgf-dashboard repo already exists."
        return
    print "\n*******************************"
    print "Cloning esgf-dashboard repo from Github"
    print "******************************* \n"
    from git import RemoteProgress
    class Progress(RemoteProgress):
        def update(self, op_code, cur_count, max_count=None, message=''):
            if message:
                print('Downloading: (==== {} ====)\r'.format(message))
                print "current line:", self._cur_line

    Repo.clone_from("https://github.com/ESGF/esgf-dashboard.git", "/usr/local/esgf-dashboard", progress=Progress())

def run_dashboard_script():
    #default values
    DashDir = "/usr/local/esgf-dashboard-ip"
    GeoipDir = "/usr/local/geoip"
    Fed="no"

    with pybash.pushd("/usr/local"):
        clone_dashboard_repo()
        os.chdir("esgf-dashboard")

        dashboard_repo_local = Repo(".")
        dashboard_repo_local.git.checkout("work_plana")

        os.chdir("src/c/esgf-dashboard-ip")

        print "\n*******************************"
        print "Running ESGF Dashboard Script"
        print "******************************* \n"

        esg_functions.stream_subprocess_output("./configure --prefix={DashDir} --with-geoip-prefix-path={GeoipDir} --with-allow-federation={Fed}".format(DashDir=DashDir, GeoipDir=GeoipDir, Fed=Fed))
        esg_functions.call_binary("make")
        esg_functions.call_binary("make", ["install"])

def main():
    setup_dashboard()


if __name__ == '__main__':
    main()
