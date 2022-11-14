import os.path
import subprocess as sp
import contextlib
import dotenv
import unittest
from typing import Dict

TESTS_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

if not TESTS_DIR.endswith("/test"):
    TESTS_DIR += "/test"

BUILD_DIR = TESTS_DIR + "/../.build"


class EndToEndTestBase(unittest.TestCase):
    release: Dict[str, str]

    @classmethod
    def _setup_env(cls):
        """
        Loads release configuration
        """
        cls.release = dotenv.dotenv_values(TESTS_DIR + "/../release.env")

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


def apply_manifests(path: str):
    sp.check_output(["kubectl", "apply", "-f", path])


def skaffold_deploy(namespace: str):
    """
    Deploy a Kubernetes application using Skaffold
    """
    sp.check_call(["skaffold", "build", "--tag", "e2e"])
    sp.check_call(["skaffold", "deploy", "--tag", "e2e", "--assume-yes=true", "-n", namespace, "--default-repo",
                   "bmt-registry:5000"])


@contextlib.contextmanager
def kubernetes_namespace(name: str):
    """
    Create a Kubernetes namespace temporarily
    """
    try:
        sp.call(["kubectl", "create", "ns", name], stderr=sp.DEVNULL, stdout=sp.DEVNULL)
        sp.check_output(["kubens", name])
        yield
    finally:
        sp.check_output(["kubectl", "delete", "ns", name, "--wait=true"])


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
