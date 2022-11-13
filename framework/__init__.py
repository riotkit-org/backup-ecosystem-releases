import os.path
import subprocess as sp
import contextlib
import dotenv
import unittest
from typing import Dict

TESTS_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
BUILD_DIR = TESTS_DIR + "/../.build"


class EndToEndTestBase(unittest.TestCase):
    release: Dict[str, str]

    @classmethod
    def _setup_env(cls):
        """
        Loads release configuration
        """
        cls.release = dotenv.dotenv_values("../release.env")

    @staticmethod
    def _setup_cluster():
        """
        Creates a new K3s cluster using K3d if existing is not active
        """

        # create a new k3d cluster if it does not exist
        sp.check_call("(docker ps | grep k3d-bmt-server-0 > /dev/null 2>&1) "
                      "|| k3d cluster create bmt --registry-create bmt-registry:0.0.0.0:5000", shell=True)

        # create a KUBECONFIG
        sp.check_output(["k3d", "kubeconfig", "merge", "bmt"])

    @staticmethod
    def _setup_hosts():
        """
        Adds an entry to /etc/hosts, so the "bm-registry" would point to a valid registry address
        """

        sp.check_call('cat /etc/hosts | grep "bm-registry" > /dev/null '
                      '|| (sudo /bin/bash -c "echo \'127.0.0.1 bm-registry\' >> /etc/hosts")', shell=True)

    @classmethod
    def setUpClass(cls) -> None:
        cls._setup_env()

        if not os.path.isdir(BUILD_DIR):
            os.mkdir(BUILD_DIR)
        os.chdir(BUILD_DIR)

        cls._setup_cluster()
        cls._setup_hosts()

    @classmethod
    def tearDownClass(cls) -> None:
        os.chdir(TESTS_DIR)


def skaffold_deploy():
    sp.check_call(["skaffold", "build"])
    sp.check_call(["skaffold", "deploy"])
    sp.check_call(["skaffold", "apply"])


@contextlib.contextmanager
def controller_repository_at_revision(version: str):
    if not os.path.isdir("backup-maker-operator"):
        sp.check_output(["git", "clone", "https://github.com/riotkit-org/backup-maker-operator"])

    pwd = os.getcwd()
    os.chdir(pwd + "/backup-maker-operator")

    try:
        sp.check_output(["git", "checkout", version])
        sp.check_call(["git", "reset", "--hard", "HEAD"])
        sp.check_call(["git", "clean", "-fx"])
        yield
    finally:
        os.chdir(pwd)
