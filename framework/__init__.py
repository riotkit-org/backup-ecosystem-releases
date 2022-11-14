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
        run("(docker ps | grep k3d-bmt-server-0 > /dev/null 2>&1) "
            "|| k3d cluster create bmt --registry-create bmt-registry:0.0.0.0:5000", shell=True)

        # create a KUBECONFIG
        run(["k3d", "kubeconfig", "merge", "bmt"])

    @staticmethod
    def _setup_hosts():
        """
        Adds an entry to /etc/hosts, so the "bm-registry" would point to a valid registry address
        """

        run('cat /etc/hosts | grep "bm-registry" > /dev/null '
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
    run(["kubectl", "apply", "-f", path])


def skaffold_deploy(namespace: str):
    """
    Deploy a Kubernetes application using Skaffold
    """
    run(["skaffold", "build", "--tag", "e2e"])
    run(["skaffold", "deploy", "--tag", "e2e", "--assume-yes=true", "-n", namespace, "--default-repo",
         "bmt-registry:5000"])


@contextlib.contextmanager
def kubernetes_namespace(name: str):
    """
    Create a Kubernetes namespace temporarily
    """
    try:
        run(["kubectl", "create", "ns", name])
        run(["kubens", name])
        yield
    finally:
        run(["kubectl", "delete", "ns", name, "--wait=true"])


@contextlib.contextmanager
def controller_repository_at_revision(version: str):
    if not os.path.isdir("backup-maker-operator"):
        run(["git", "clone", "https://github.com/riotkit-org/backup-maker-operator"])

    pwd = os.getcwd()
    os.chdir(pwd + "/backup-maker-operator")

    try:
        run(["git", "checkout", version])
        run(["git", "reset", "--hard", "HEAD"])
        run(["git", "clean", "-fx"])
        yield
    finally:
        os.chdir(pwd)


def run(*popenargs, **kwargs):
    try:
        sp.check_output(*popenargs, **kwargs, stderr=sp.STDOUT)
    except sp.CalledProcessError as err:
        print(err.output)
        raise err
