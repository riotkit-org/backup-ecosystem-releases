import os.path
import subprocess
import subprocess as sp
import contextlib
import dotenv
import unittest
import _portforward as portforward
import portforward as portforwardpub
from typing import Dict, Union, List

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

        # append GOROOT/bin to the path for the Skaffold's KO builder which not always can find right Go binary
        if "GOROOT" in os.environ:
            os.environ["PATH"] = os.environ["PATH"] + ":" + os.environ["GOROOT"] + "/bin"

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

    def skaffold_deploy(self, skip_when: bool = None):
        """
        Deploy a Kubernetes application using Skaffold
        """

        if skip_when:
            print(f"Skipping skaffold in {os.getcwd()}")
            return

        print(f"Running skaffold in {os.getcwd()}")

        assert os.path.isfile("skaffold.yaml"), "Cannot find skaffold.yaml in " + os.getcwd()

        with open("skaffold.yaml", "r") as f:
            content = f.read()

        if "build:" in content:
            run(["skaffold", "build",
                 "--tag", "e2e",
                 "--default-repo", "bmt-registry:5000",
                 "--push",
                 "--insecure-registry", "bmt-registry:5000", "--disable-multi-platform-build=true",
                 "--detect-minikube=false", "--cache-artifacts=false"])

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

    def kubectl(self, popenargs: Union[str, List[str]], **kwargs) -> str:
        """
        Executes a kubectl command and returns output
        """
        if type(popenargs) == list:
            if "kubectl" not in popenargs:
                popenargs = ["kubectl"] + popenargs
            if "-n" not in popenargs and "--namespace" not in popenargs:
                popenargs = popenargs + ["-n", self.current_ns]
        else:
            if "kubectl" not in popenargs:
                popenargs = "kubectl " + popenargs
            if "-n " not in popenargs and "--namespace " not in popenargs:
                popenargs += " -n " + self.current_ns + " "

        return sp.check_output(popenargs, **kwargs, timeout=None).decode('utf-8')

    def logs(self, pod_label: str, ns: str, allow_failure: bool = True):
        """
        Shows logs
        """
        try:
            print(f" >>> Logs: {pod_label} from '{ns}' namespace")
            print(self.kubectl(["logs", "-l", pod_label, "-n", ns]))
        except:
            if allow_failure:
                raise

    def apply_manifests(self, path: str, ns: str = ''):
        """
        Applies a file or directory to Kubernetes
        """
        if not ns:
            ns = self.current_ns
        run(["kubectl", "apply", "-f", path, "-n", ns])

    def apply_yaml(self, yaml: str, ns: str = ''):
        """
        Applies a plain YAML on Kubernetes from stdin
        """
        if not ns:
            ns = self.current_ns

        yaml = yaml.strip()

        try:
            run(["kubectl", "apply", "-f", "-", "-n", ns], input=yaml.encode('utf-8'))
        except:
            print(yaml)
            raise

    @staticmethod
    def port_forward(local_port: int, remote_port: int, pod_label: str, ns: str, retry_left: int = 5) -> None:
        pod_name = "?"
        try:
            try:
                pod_name = sp.check_output(["kubectl", "get", "pod", "-l", pod_label, "-n", ns, "-o", "name"]) \
                    .replace(b"pod/", b"", 1).decode("utf-8").strip()
            except sp.CalledProcessError:
                raise Exception(f"Cannot make a port-forward, Pod not found for label {pod_label}")

            try:
                portforward.stop(ns, pod_name)
            except:
                pass
            portforward.forward(ns, pod_name, local_port, remote_port,
                                portforwardpub._config_path(None),
                                portforwardpub.LogLevel.ERROR.value)
        except:
            if retry_left > 0:
                print(f"pod_name: {pod_name}")
                EndToEndTestBase.port_forward(local_port, remote_port, pod_label, ns, retry_left-1)
                return
            raise


@contextlib.contextmanager
def cloned_repository_at_revision(url: str, version: str):
    repo_name = url.split("/")[-1].replace(".git", "")

    pwd = os.getcwd()

    if not os.path.isdir(BUILD_DIR + "/" + repo_name):
        os.chdir(BUILD_DIR)
        run(["git", "clone", url])

    try:
        os.chdir(BUILD_DIR + "/" + repo_name)
        run(["git", "checkout", version])
        is_not_on_branch = sp.check_output(["git", "rev-parse",
                                            "--abbrev-ref", "--symbolic-full-name", "HEAD"]).strip() == b"HEAD"

        if os.getenv("SKIP_GIT_PULL") == "true":
            print("Skipping git pull because of SKIP_GIT_PULL=true")
        elif os.path.islink(BUILD_DIR + "/" + repo_name):
            print(f"Skipping git pull because {BUILD_DIR}/{repo_name} is a link")
        elif is_not_on_branch:
            print("Skipping git pull, because we are not on a branch right now")
        else:
            run(["git", "pull"])
            run(["git", "reset", "--hard", "HEAD"])
            run(["git", "clean", "-fx"])
        yield
    finally:
        os.chdir(pwd)


def run(*popenargs, **kwargs):
    try:
        out = sp.check_output(*popenargs, **kwargs, stderr=sp.STDOUT)
        if os.getenv('VERBOSE') == "true":
            print(out.decode('utf-8'))
    except sp.CalledProcessError as err:
        print(err.output.decode('utf-8'))
        raise err
