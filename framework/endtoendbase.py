import os.path
import subprocess
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
    current_ns: str

    @classmethod
    def _setup_env(cls):
        """
        Loads release configuration
        """
        cls.release = dotenv.dotenv_values(TESTS_DIR + "/../release.env")
        os.environ["PATH"] = BUILD_DIR + ":" + os.getenv("PATH")

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

    def setUp(self) -> None:
        self.current_ns = "default"

    @classmethod
    def tearDownClass(cls) -> None:
        os.chdir(TESTS_DIR)

    @contextlib.contextmanager
    def in_dir(self, path: str):
        prev_cwd = os.getcwd()
        try:
            os.chdir(TESTS_DIR + "/../" + path)
            yield
        finally:
            os.chdir(prev_cwd)

    @contextlib.contextmanager
    def kubernetes_namespace(self, name: str, persistent: bool = False):
        """
        Create a Kubernetes namespace temporarily
        """
        prev_ns = self.current_ns

        try:
            self.current_ns = name
            sp.call(["kubectl", "create", "ns", name], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            run(["kubens", name])
            yield
        finally:
            if not persistent:
                self.current_ns = prev_ns
                run(["kubectl", "delete", "ns", name, "--wait=true"])

    def skaffold_deploy(self):
        """
        Deploy a Kubernetes application using Skaffold
        """
        assert os.path.isfile("skaffold.yaml"), "Cannot find skaffold.yaml in " + os.getcwd()

        with open("skaffold.yaml", "r") as f:
            content = f.read()

        if "build:" in content:
            run(["skaffold", "build",
                 "--tag", "e2e",
                 "--default-repo", "bmt-registry:5000",
                 "--push",
                 "--insecure-registry", "bmt-registry:5000"])

        run(["skaffold", "deploy", "--tag", "e2e", "--assume-yes=true", "--default-repo",
             "bmt-registry:5000"])

    def has_pod_with_label_present(self, label: str, ns: str = '') -> bool:
        """
        Is there a Pod labelled?
        """
        if not ns:
            ns = self.current_ns

        try:
            run(["kubectl", "get", "pods", "-n", ns, "-l", label])
            return True
        except subprocess.CalledProcessError:
            return False

    def apply_manifests(self, path: str, ns: str = ''):
        if not ns:
            ns = self.current_ns
        run(["kubectl", "apply", "-f", path, "-n", ns])


@contextlib.contextmanager
def cloned_repository_at_revision(url: str, version: str):
    repo_name = url.split("/")[-1].replace(".git", "")
    if not os.path.isdir(repo_name):
        run(["git", "clone", url])

    pwd = os.getcwd()
    os.chdir(pwd + "/" + repo_name)

    try:
        run(["git", "checkout", version])
        run(["git", "pull"])
        run(["git", "reset", "--hard", "HEAD"])
        run(["git", "clean", "-fx"])
        yield
    finally:
        os.chdir(pwd)


def run(*popenargs, **kwargs):
    try:
        sp.check_output(*popenargs, **kwargs, stderr=sp.STDOUT)
    except sp.CalledProcessError as err:
        print(err.output.decode('utf-8'))
        raise err
