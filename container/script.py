"""Entrypoint script for starting a mongod Docker container."""

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import psutil
import yaml

"""
ENTRYPOINT SCRIPT OVERVIEW:

This entrypoint script has been converted from a shell script to a Python script. Docker
wrote the original shell script which provided users with an interface to customize their mongodb
docker containers. This Python script has been written to be backwards compatible with Docker's
original entrypoint script so that users can easily switch to these new images with minimal changes.

Here are some things that this script does to keep note of:

1. If the docker container is started as the 'root' user, the script will automatically switch
users to the 'mongodb' user. Before switching, the script will ensure that the 'mongodb' user has
all of the proper permissions to read data files & write to stdout/stderr. If the 'mongodb' user
does not have permission to write to stdout/stderr, it will write to a log file instead.

2. The script will also perform an 'initialize database' step, which create an 'admin' user using
the 'MONGODB_INITDB_ROOT_USERNAME' and 'MONGODB_INITDB_ROOT_PASSWORD' environment variables. You can
also place those secrets in files & set 'MONGODB_INITDB_ROOT_USERNAME_FILE' and
'MONGODB_INITDB_ROOT_PASSWORD_FILE' to those filenames. The 'initialize database' step will also run
any .sh & .js scripts that the user has in the '/docker-entrypoint-initdb.d'
directory. If the database has already been initialized, it will not run this step again.

3. Steps (1) and (2) will run only if needed. After those optional steps are completed, the mongodb
Docker container will officially start with the desired configuration.
"""

################################# UTIL FUNCTIONS ###################################

ARCHITECTURE_WARNINGS = {
    "amd64": {
        "regex": "^flags.* avx( .*|$)",
        "warning": "WARNING: MongoDB 5.0+ requires a CPU with AVX support, and your current system does not appear to have that!",
    },
    "arm64": {
        "regex": "^Features.* (fphp|dcpop|sha3|sm3|sm4|asimddp|sha512|sve)( .*|$)",
        "warning": "WARNING: MongoDB 5.0+ requires ARMv8.2-A or higher, and your current system does not appear to implement any of the common features for that!",
    },
}

KERNEL_VERSION_CUTOFF = (6, 19)
GLIBC_TUNABLES_ENV_VAR = "GLIBC_TUNABLES"
GLIBC_RSEQ_TUNABLE = "glibc.pthread.rseq"


def print_system_architecture_warning() -> None:
    """Print architecture compatibility warning if it applies."""
    regex = ARCHITECTURE_WARNINGS.get(platform.processor(), {}).get("regex", None)
    if regex and any([re.search(regex, line) for line in open("/proc/cpuinfo")]):
        print(ARCHITECTURE_WARNINGS[platform.processor()])


def parse_kernel_version(release: str) -> Optional[Tuple[int, int]]:
    """Parse the major/minor parts of a Linux kernel release string."""
    match = re.match(r"^([0-9]+)\.([0-9]+)", release)
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)))


def is_truthy(value: Optional[str]) -> bool:
    """Return True when an environment variable value should be interpreted as enabled."""
    return bool(value and value.strip().lower() in {"1", "true", "yes", "on"})


def set_glibc_tunable(name: str, value: str) -> None:
    """Set or replace a single GLIBC tunable while preserving any others."""
    tunables = [tunable for tunable in os.environ.get(GLIBC_TUNABLES_ENV_VAR, "").split(":") if tunable]
    updated_tunables = []
    replaced = False

    for tunable in tunables:
        key, _, _ = tunable.partition("=")
        if key == name:
            updated_tunables.append(f"{name}={value}")
            replaced = True
        else:
            updated_tunables.append(tunable)

    if not replaced:
        updated_tunables.append(f"{name}={value}")

    os.environ[GLIBC_TUNABLES_ENV_VAR] = ":".join(updated_tunables)


def enforce_kernel_compatibility() -> None:
    """Stop startup on unsupported kernels unless an explicit degraded-performance bypass is set."""
    kernel_release = platform.release()
    kernel_version = parse_kernel_version(kernel_release)
    if kernel_version is None or kernel_version < KERNEL_VERSION_CUTOFF:
        return

    print(
        (
            f"ERROR: Detected Linux kernel {kernel_release}. MongoDB 8.0+ utilizes the tcmalloc allocator which has a known issue "
            f"with the v{KERNEL_VERSION_CUTOFF[0]}.{KERNEL_VERSION_CUTOFF[1]} and newer Linux kernel. This "
            f"container will not start by default on v{KERNEL_VERSION_CUTOFF[0]}.{KERNEL_VERSION_CUTOFF[1]}+."
        ),
        file=sys.stderr,
    )
    sys.exit(1)


# Environment variables used for auth
MONGODB_USERNAME_ENV_VARS = (
    "MONGODB_INITDB_ROOT_USERNAME",
    "MONGO_INITDB_ROOT_USERNAME",
)
MONGODB_PASSWORD_ENV_VARS = (
    "MONGODB_INITDB_ROOT_PASSWORD",
    "MONGO_INITDB_ROOT_PASSWORD",
)

# Environment variables used for init db
MONGODB_INITDB_ENV_VARS = ("MONGODB_INITDB_DATABASE", "MONGO_INITDB_DATABASE")
MONGODB_INITDB_REPL_SET_ENV_VARS = ("MONGODB_INITDB_REPL_SET_HOST", "MONGO_INITDB_REPL_SET_HOST")


def auth_enabled() -> bool:
    """Check environment variables to see if this container uses auth."""
    # DISCLAIMER: This should only be run after _setup_environment() is called
    return bool(
        os.environ.get(
            MONGODB_USERNAME_ENV_VARS[0],
            os.environ.get(MONGODB_USERNAME_ENV_VARS[1], False),
        )
        and os.environ.get(
            MONGODB_PASSWORD_ENV_VARS[0],
            os.environ.get(MONGODB_PASSWORD_ENV_VARS[1], False),
        )
    )


MONGODB_SHELL = shutil.which("mongo") or shutil.which("mongosh")
assert MONGODB_SHELL is not None


def ensure_mongod_process_running(host: str, port: str, exp: str = "db.hello()", is_init: bool = False):
    """Check whether mongod process is running within timeout period."""
    timeout = time.time() + 30
    cmd = [
        MONGODB_SHELL,
        "--host",
        host,
        "--port",
        port,
        "--quiet",
        "admin",
        "--eval",
        f'"{exp}"',
    ]
    if not is_init and tls_required():
        # allowConnectionsWithoutCertificats should be true allowing us to ignore invalid certs
        cmd += ["--tls", "--tlsAllowInvalidCertificates"]
    while True:
        if time.time() > timeout:
            print("error: mongod still not running after 30 second(s).")
            print(
                "Take a look at your mongod configuration to see if something is wrong.",
                file=sys.stderr,
            )
            exit(1)
        try:
            assert MONGODB_SHELL is not None
            subprocess.run(
                cmd,  # type: ignore[arg-type]
                check=True,
            )
            break
        except subprocess.CalledProcessError:
            print("Warning: mongod not running yet.")
            time.sleep(1)


def can_write_to_stdout() -> bool:
    """Check if the current process can write to stdout."""
    return os.access(f"/proc/{os.getpid()}/fd/1", os.W_OK)


def has_bind_ip() -> bool:
    """Check whether --bind_ip or --bind_ip_all has been set."""
    args = get_entrypoint_args()
    config_dict = get_config_as_dict()
    return any(
        [
            args.bind_ip,
            args.bind_ip_all,
            config_dict.get("net", {}).get("bindIp", None),
            config_dict.get("net", {}).get("bindIpAll", None),
        ]
    )


def get_config_host_port() -> Tuple[Optional[str], Optional[str]]:
    config_dict = get_config_as_dict()
    ip = config_dict.get("net", {}).get("bindIp", None)
    port = config_dict.get("net", {}).get("port", None)
    if port:
        port = str(port)
    return (ip, port)


def get_replica_set_name() -> Optional[str]:
    config_dict = get_config_as_dict()
    return config_dict.get("replication", {}).get("replSetName", None)


################################# FUNCTIONS FOR INITIALIZE DB #####################################

INITDB_SCRIPTS_FILEPATH = "/docker-entrypoint-initdb.d"


def get_init_db_scripts() -> List[str]:
    """Get scripts from the initdb scripts directory."""
    if os.path.exists(INITDB_SCRIPTS_FILEPATH):
        return [
            os.path.join(INITDB_SCRIPTS_FILEPATH, filename)
            for filename in sorted(os.listdir(INITDB_SCRIPTS_FILEPATH))
            if filename.endswith(".sh") or filename.endswith(".js")
        ]
    return []


def has_been_initialized() -> bool:
    """Check if certain files exist in the dbpath indicating db has already been initialized."""
    db_path = resolve_db_path()
    for path in [
        "WiredTiger",
        "journal",
        "local.0",
        "storage.bson",
    ]:
        if os.path.exists(os.path.join(db_path, path)):
            return True
    return False


def requires_initialization() -> bool:
    """Determine whether desired command line will require initialization or not."""
    return bool(
        ((auth_enabled() or get_init_db_scripts()) and not has_been_initialized()) and get_executable() == "mongod"
    )


INITDB_CONFIG_FILEPATH = "/tmp/docker-entrypoint-temp-config.json"
INITDB_LOG_FILEPATH = "docker-initdb.log"
INITDB_HOST = "127.0.0.1"
INITDB_PORT = "27017"


def get_init_db_command_line() -> List[str]:
    """Get the command line to start a 'mongod' for db initialization."""
    init_db_arguments: List[str] = []
    for arg, value in vars(get_init_db_args()).items():
        if arg == "EXECUTABLE":
            init_db_arguments = [shutil.which(value)] + init_db_arguments
        elif value is True:
            init_db_arguments += [f"--{arg}"]
        elif value:
            init_db_arguments += [f"--{arg}", value]
        else:
            # If the value is False, the arg is a "flag" which should not be set.
            # If the value is None, the arg is an "option" with no real value & should not be used.
            # In both cases, we should exclude these args.
            continue
    return init_db_arguments


def get_auth_credentials() -> Tuple[Optional[str], Optional[str]]:
    username = os.environ.get(
        MONGODB_USERNAME_ENV_VARS[0],
        os.environ.get(MONGODB_USERNAME_ENV_VARS[1], None),
    )
    password = os.environ.get(
        MONGODB_PASSWORD_ENV_VARS[0],
        os.environ.get(MONGODB_PASSWORD_ENV_VARS[1], None),
    )
    return username, password


def requires_replica_set_init(host: str, port: str):
    replicaset_js_code = ""
    if auth_enabled():
        username, password = get_auth_credentials()
        replicaset_js_code += f'db.auth("{username}", "{password}");'
    replicaset_js_code += """
    rs.status();
    """
    cmd = [
        MONGODB_SHELL,
        "--host",
        host,
        "--port",
        port,
        "--quiet",
        "admin",
        "--eval",
        replicaset_js_code,
    ]

    if tls_required():
        # allowConnectionsWithoutCertificats should be true allowing us to ignore invalid certs
        cmd += ["--tls", "--tlsAllowInvalidCertificates"]

    try:
        assert MONGODB_SHELL is not None
        subprocess.run(
            cmd,  # type: ignore[arg-type]
            check=True,
        )
    except subprocess.CalledProcessError:
        print("Replica set status check failed. Attempting to init...")
        return True

    return False


def initiate_replica_set(host: str, port: str, repl_member_host_port: str):
    """Custom add-on function: Initiate a replicaSet if necessary"""

    if not requires_replica_set_init(host, port):
        return
    rs = get_replica_set_name()
    assert rs
    replicaset_js_code = ""
    if auth_enabled():
        username, password = get_auth_credentials()
        replicaset_js_code += f'db.auth("{username}", "{password}");'
    replicaset_js_code += f"""
    var config = {{
      "_id": "{rs}",
      "version": 1,
      "members": [
        {{
          "_id": 1,
          "host": "{repl_member_host_port}"
        }}
      ]
    }};
    rs.initiate(config, {{ force: true }});
    """
    cmd = [
        MONGODB_SHELL,
        "--host",
        host,
        "--port",
        port,
        "--quiet",
        "admin",
        "--eval",
        replicaset_js_code,
    ]

    if tls_required():
        # allowConnectionsWithoutCertificats should be true allowing us to ignore invalid certs
        cmd += ["--tls", "--tlsAllowInvalidCertificates"]
    try:
        assert MONGODB_SHELL is not None
        subprocess.run(
            cmd,  # type: ignore[arg-type]
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print("Could not initiate replicaset")
        print(f"Ran: {' '.join(cmd)}")  # type: ignore[arg-type]
        print(
            "Take a look at your replicaset configuration to see if something is wrong.",
            file=sys.stderr,
        )
        exit(exc.returncode)


def _init_database() -> None:
    """Initialize db if needed."""
    if not requires_initialization():
        return

    # start an init db mongod
    forked_init_db_command_line = get_init_db_command_line() + ["--fork"]
    try:
        subprocess.run(
            forked_init_db_command_line,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print("Could not init database.")
        print(forked_init_db_command_line)
        print(f"Subprocess failed with errorcode {exc.returncode}")
        print(
            "Take a look at your mongod configuration to see if something is wrong.",
            file=sys.stderr,
        )
        exit(exc.returncode)

    ensure_mongod_process_running(INITDB_HOST, INITDB_PORT, is_init=True)

    # create auth user
    if auth_enabled():
        username, password = get_auth_credentials()
        try:
            assert MONGODB_SHELL is not None
            p = subprocess.Popen(
                [
                    MONGODB_SHELL,
                    "--host",
                    INITDB_HOST,
                    "--port",
                    INITDB_PORT,
                    "--quiet",
                    "admin",
                ],
                stdin=subprocess.PIPE,
                universal_newlines=True,
            )
            p.communicate(
                input=f"db.createUser({{user: `{username}`, pwd: `{password}`, roles: [{{role: 'root', db: 'admin'}}]}})"
            )
            p.kill()
        except subprocess.SubprocessError:
            print("Could not create admin user during database initialization.")
            print(
                "Take a look at your mongod configuration to see if something is wrong.",
                file=sys.stderr,
            )
            p.kill()
            exit(p.returncode)

    # run initdb scripts
    for script in get_init_db_scripts():
        if script.endswith(".sh"):
            try:
                subprocess.run(["/bin/bash", script], check=True)
            except subprocess.CalledProcessError as exc:
                print("Could not run shell script during database initialization.")
                print(f"Checkout the following file: {script}")
                exit(exc.returncode)
        elif script.endswith(".js"):
            try:
                assert MONGODB_SHELL is not None
                subprocess.run(
                    [
                        MONGODB_SHELL,
                        "--host",
                        INITDB_HOST,
                        "--port",
                        INITDB_PORT,
                        "--quiet",
                        os.environ.get(
                            MONGODB_INITDB_ENV_VARS[0],
                            os.environ.get(MONGODB_INITDB_ENV_VARS[1], ""),
                        ),
                        script,
                    ],
                    check=True,
                )
            except subprocess.CalledProcessError as exc:
                print("Could not run js script during database initialization.")
                print(f"Checkout the following file: {script}")
                exit(exc.returncode)

    # shutdown the mongod used for init
    # don't use check=True in subprocess -- mongosh does not exit with 0 for db.shutdownServer()
    assert MONGODB_SHELL is not None
    subprocess.run(
        [
            MONGODB_SHELL,
            "--host",
            INITDB_HOST,
            "--port",
            INITDB_PORT,
            "admin",
            "--eval",
            "db.shutdownServer()",
        ],
    )

    # Ensure that the init mongod process has stopped.
    # It will be a zombie process because this script is the parent process.
    assert "mongod" not in [
        proc.name() for proc in psutil.process_iter() if proc.status() != psutil.STATUS_ZOMBIE
    ], "Could not shutdown mongod for init db successfully. Try again."

    print("MongoDB init process complete; ready for start up.")


def followup_config(repl_member_host_port: Optional[str]) -> None:
    host, port = get_config_host_port()
    # Can't connect to 0.0.0.0
    if host == "0.0.0.0":
        host = "localhost"
    if not host:
        host = INITDB_HOST
    if not port:
        port = INITDB_PORT

    if repl_member_host_port:
        ensure_mongod_process_running(host, port)
        initiate_replica_set(host, port, repl_member_host_port)


####################### FUNCTIONS THAT AFFECT STATE (SETUP & CLEANUP) #############################

DEFAULT_DBPATH = "/data/db"
DEFAULT_CONFIG_DBPATH = "/data/configdb"


def _set_environment_variable_from_file(environment_var: str) -> None:
    """Set the environment variable from a file if needed."""
    # Get the environment variable data
    environment_var_value = os.environ.get(environment_var, None)

    # Get the corresponding file variable data
    environment_file_var = f"{environment_var}_FILE"
    if environment_file_var.startswith("MONGO_"):
        replacement = environment_file_var.replace("MONGO_", "MONGODB_")
        print(
            f"Warning: File {environment_file_var} is deprecated. Use {replacement} instead.",
            file=sys.stderr,
        )

    environment_file_var_value = os.environ.get(environment_file_var, None)

    # Ensure both environment variable and environment variable file are not set
    assert not (
        environment_var_value and environment_file_var_value
    ), f"Cannot set environment variable & set environment variable file: {environment_var} & {environment_file_var} both set."

    # Set the environment variable from file
    if environment_file_var_value:
        with open(environment_file_var_value, "r") as secret:
            os.environ[environment_var] = secret.read()


def _setup_auth_environment_variables() -> None:
    """Setup the user and pass environment variables."""
    if os.environ.get(MONGODB_USERNAME_ENV_VARS[1]) is not None:
        print(
            (
                f"Warning: Environment variable {MONGODB_USERNAME_ENV_VARS[1]} is deprecated."
                f"Use {MONGODB_USERNAME_ENV_VARS[0]} instead."
            )
        )
    if os.environ.get(MONGODB_PASSWORD_ENV_VARS[1]) is not None:
        print(
            (
                f"Warning: Environment variable {MONGODB_PASSWORD_ENV_VARS[1]} is deprecated."
                f"Use {MONGODB_PASSWORD_ENV_VARS[0]} instead."
            )
        )

    _set_environment_variable_from_file(MONGODB_USERNAME_ENV_VARS[0])
    if os.environ.get(MONGODB_USERNAME_ENV_VARS[0]) is None:
        _set_environment_variable_from_file(MONGODB_USERNAME_ENV_VARS[1])

    _set_environment_variable_from_file(MONGODB_PASSWORD_ENV_VARS[0])
    if os.environ.get(MONGODB_PASSWORD_ENV_VARS[0]) is None:
        _set_environment_variable_from_file(MONGODB_PASSWORD_ENV_VARS[1])

    assert (
        os.environ.get(
            MONGODB_USERNAME_ENV_VARS[0],
            os.environ.get(MONGODB_USERNAME_ENV_VARS[1], None),
        )
        and os.environ.get(
            MONGODB_PASSWORD_ENV_VARS[0],
            os.environ.get(MONGODB_PASSWORD_ENV_VARS[1], None),
        )
    ) or (
        not os.environ.get(
            MONGODB_USERNAME_ENV_VARS[0],
            os.environ.get(MONGODB_USERNAME_ENV_VARS[1], None),
        )
        and not os.environ.get(
            MONGODB_PASSWORD_ENV_VARS[0],
            os.environ.get(MONGODB_PASSWORD_ENV_VARS[1], None),
        )
    ), f"Must set both or neither: {MONGODB_USERNAME_ENV_VARS[0]} & {MONGODB_PASSWORD_ENV_VARS[0]}"


def _setup_all_environment_variables() -> None:
    """Setup all environment variables for the lifetime of this script."""
    _setup_auth_environment_variables()
    os.environ.setdefault(MONGODB_INITDB_ENV_VARS[0], "test")


def _generate_init_config_file() -> None:
    """Generate a new, modified config file for db initialization."""
    if not requires_initialization():
        return
    config_as_dict = get_config_as_dict()
    for field in [
        "systemLog",
        "processManagement",
        "net",
        "security",
        "replication",
    ]:
        config_as_dict.pop(field, None)
    with open(INITDB_CONFIG_FILEPATH, "w") as init_config_file:
        yaml.dump(config_as_dict, init_config_file)


def _setup_environment() -> None:
    """Setup environment before starting the script."""
    _setup_all_environment_variables()
    _generate_init_config_file()


def _clean_environment() -> None:
    """Clean up environment before starting main process."""
    if os.path.exists(INITDB_CONFIG_FILEPATH):
        os.unlink(INITDB_CONFIG_FILEPATH)


####################### FUNCTIONS TO GET ORIGINAL ARGS PASSED IN ##################################


def get_config_as_dict() -> Dict[str, Any]:
    """Return a dictionary representing the config file."""
    config_path = get_entrypoint_args().config
    if not config_path:
        return {}

    with open(config_path, "r") as config_file:
        return yaml.safe_load(config_file)


def resolve_db_path() -> str:
    """Get the db path for this mongod command line."""
    entrypoint_arguments = get_entrypoint_args()
    config = get_config_as_dict()

    if entrypoint_arguments.dbpath:
        return entrypoint_arguments.dbpath
    elif config.get("storage", {}).get("dbPath", None):
        return config["storage"]["dbPath"]
    elif entrypoint_arguments.configsvr or config.get("sharding", {}).get("clusterRole", None) == "configsvr":
        return DEFAULT_CONFIG_DBPATH
    else:
        return DEFAULT_DBPATH


def tls_required() -> bool:
    entrypoint_args = get_entrypoint_args()
    config = get_config_as_dict()
    return (
        entrypoint_args.tlsMode == "requireTLS"
        or config.get("net", {}).get("tls", {}).get("mode", None) == "requireTLS"
    )


def get_tls_key_paths() -> Tuple[str, str]:
    entrypoint_args = get_entrypoint_args()
    config = get_config_as_dict()

    cert = entrypoint_args.tlsCertificateKeyFile
    ca = entrypoint_args.tlsCAFile
    if not cert:
        cert = config.get("net", {}).get("tls", {}).get("certificateKeyFile", None)
    if not ca:
        ca = config.get("net", {}).get("tls", {}).get("CAFile", None)

    return cert, ca


def get_final_command_line_args() -> List[str]:
    """Get the full command line args with final settings."""
    args = get_command_line_args()
    if auth_enabled():
        args.append("--auth")
    if not has_bind_ip():
        args.append("--bind_ip_all")
    return args


def get_command_line_args() -> List[str]:
    """Get the full command line args with the executable as the first element in the list."""
    argument_list = sys.argv[1:]
    # Default to 'mongod' if no command exists
    if not argument_list or argument_list[0].startswith("-"):
        mongod_path = shutil.which("mongod")
        assert mongod_path is not None
        return [mongod_path] + argument_list
    return argument_list


def get_executable() -> str:
    """Get the executable for this command line."""
    return os.path.basename(get_command_line_args()[0])


def get_init_db_args() -> argparse.Namespace:
    """Parse the arguments using the init db parser."""
    init_db_parser = get_init_db_parser()
    init_db_args, _ = init_db_parser.parse_known_args(get_command_line_args())
    return init_db_args


def get_entrypoint_args() -> argparse.Namespace:
    """Parse the arguments using the entrypoint parser."""
    entrypoint_parser = get_entrypoint_parser()
    entrypoint_args, _ = entrypoint_parser.parse_known_args(get_command_line_args())
    return entrypoint_args


#############################################################################
"""
PARSER NOTES:

Definitions:
    - option: an argument that takes in a value. ie: --option1 value1 --option2 value2
        - the value will be stored as a "string" if it is set or "None" if it is not.
        - ie: {"option1": "value1", "option2": "value2", "option3": None}
    - flag: an argument that is True when it is included & False otherwise. ie: --flag1 --flag2
        - the value will always be stored as a "boolean" & must be True or False
        - ie: {"flag1": True, "flag2": True, "flag3": False}
    - EXECUTABLE: this is a special positional argument & should be a 'mongo*' binary in most cases.
        - this will default to 'mongod' if no binary is present as the first argument.
"""

####################### ENTRYPOINT PARSER ###################################


def get_entrypoint_parser() -> argparse.ArgumentParser:
    """Get a parser to parse arguments for the Docker entrypoint script."""
    parser = argparse.ArgumentParser(allow_abbrev=False, conflict_handler="resolve")
    parser.add_argument(
        "EXECUTABLE",
        nargs="?",
        help="The name of the executable to run in the Docker container. Defaults to 'mongod' if none provided.",
    )
    parser.add_argument(
        "--config",
        "-f",
        default=None,
    )
    parser.add_argument(
        "--tlsCertificateKeyFile",
        default=None,
    )
    parser.add_argument(
        "--tlsCAFile",
        default=None,
    )
    parser.add_argument(
        "--dbpath",
        default=None,
    )
    parser.add_argument(
        "--configsvr",
        action="store_true",
    )
    parser.add_argument(
        "--bind_ip",
        default=None,
    )
    parser.add_argument(
        "--bind_ip_all",
        action="store_true",
    )
    parser.add_argument(
        "--tlsMode",
        default=None,
    )
    parser.add_argument(
        "--replSetMember",
        default=None,
        help="Initiate a replica set member given a host name.",
    )
    return parser


####################### INITDB PARSER ###################################

INIT_DB_CONFIG = INITDB_CONFIG_FILEPATH if get_entrypoint_args().config else None
INIT_DB_TLS_MODE = "allowTLS" if get_entrypoint_args().tlsCertificateKeyFile else "disabled"
INIT_DB_LOGPATH = (
    f"/proc/{os.getpid()}/fd/1" if can_write_to_stdout() else os.path.join(resolve_db_path(), INITDB_LOG_FILEPATH)
)


def get_init_db_parser() -> argparse.ArgumentParser:
    """Get a parser to parse arguments for initializing the database."""
    parser = get_entrypoint_parser()
    parser.add_argument(
        "--bind_ip",
        action="store_const",
        const=INITDB_HOST,
        default=INITDB_HOST,
    )
    parser.add_argument(
        "--port",
        action="store_const",
        const=INITDB_PORT,
        default=INITDB_PORT,
    )
    parser.add_argument(
        "--bind_ip_all",
        action="store_const",
        const=False,
        default=False,
    )
    parser.add_argument(
        "--auth",
        action="store_const",
        const=False,
        default=False,
    )
    parser.add_argument(
        "--keyFile",
        action="store_const",
        const=None,
        default=None,
    )
    parser.add_argument(
        "--logappend",
        action="store_const",
        const=True,
        default=True,
    )
    parser.add_argument(
        "--config",
        "-f",
        action="store_const",
        const=INIT_DB_CONFIG,
        default=INIT_DB_CONFIG,
    )
    parser.add_argument(
        "--tlsMode",
        action="store_const",
        const=INIT_DB_TLS_MODE,
        default=INIT_DB_TLS_MODE,
    )
    parser.add_argument(
        "--logpath",
        action="store_const",
        const=INIT_DB_LOGPATH,
        default=INIT_DB_LOGPATH,
    )
    return parser


def parse_replica_set_arg() -> Optional[str]:
    """Check for replicaset arg and remove if present."""
    argument_list = sys.argv[1:]
    entrypoint_parser = get_entrypoint_parser()
    entrypoint_args, _ = entrypoint_parser.parse_known_args(argument_list)
    replicaset_host = entrypoint_args.replSetMember
    if replicaset_host:
        try:
            # Remove meta entrypoint args
            sys.argv.remove(f"--replSetMember={replicaset_host}")
        except Exception:
            pass
    else:
        replicaset_host = os.environ.get(
            MONGODB_INITDB_REPL_SET_ENV_VARS[0],
            os.environ.get(MONGODB_INITDB_REPL_SET_ENV_VARS[1], None),
        )

    return replicaset_host


####################### MAIN FUNCTION ###################################

if __name__ == "__main__":
    print_system_architecture_warning()
    if get_executable() == "mongod":
        enforce_kernel_compatibility()
        repl_member_host_port = parse_replica_set_arg()
        _setup_environment()
        _init_database()
        _clean_environment()
        p = subprocess.Popen(get_final_command_line_args(), stdout=sys.stdout, stderr=sys.stderr)
        followup_config(repl_member_host_port)
        p.wait()
    else:
        subprocess.run(get_command_line_args(), check=True)
