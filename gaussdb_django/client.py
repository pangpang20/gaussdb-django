import signal

from django.db.backends.base.client import BaseDatabaseClient


class DatabaseClient(BaseDatabaseClient):
    executable_name = "gsql"

    @classmethod
    def settings_to_cmd_args_env(cls, settings_dict, parameters):
        args = [cls.executable_name]
        options = settings_dict["OPTIONS"]

        host = settings_dict.get("HOST")
        port = settings_dict.get("PORT")
        dbname = settings_dict.get("NAME")
        user = settings_dict.get("USER")
        passwd = settings_dict.get("PASSWORD")
        passfile = options.get("passfile")
        service = options.get("service")
        sslmode = options.get("sslmode")
        sslrootcert = options.get("sslrootcert")
        sslcert = options.get("sslcert")
        sslkey = options.get("sslkey")

        if not dbname and not service:
            # Connect to the default 'postgres' db.
            dbname = "postgres"
        if user:
            args += ["-U", user]
        if host:
            args += ["-h", host]
        if port:
            args += ["-p", str(port)]
        args.extend(parameters)
        if dbname:
            args += [dbname]

        env = {}
        if passwd:
            env["GAUSSDBPASSWORD"] = str(passwd)
        if service:
            env["GAUSSDBSERVICE"] = str(service)
        if sslmode:
            env["GAUSSDBSSLMODE"] = str(sslmode)
        if sslrootcert:
            env["GAUSSDBSSLROOTCERT"] = str(sslrootcert)
        if sslcert:
            env["GAUSSDBSSLCERT"] = str(sslcert)
        if sslkey:
            env["GAUSSDBSSLKEY"] = str(sslkey)
        if passfile:
            env["GAUSSDBPASSFILE"] = str(passfile)
        return args, (env or None)

    def runshell(self, parameters):
        sigint_handler = signal.getsignal(signal.SIGINT)
        try:
            # Allow SIGINT to pass to psql to abort queries.
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            super().runshell(parameters)
        finally:
            # Restore the original SIGINT handler.
            signal.signal(signal.SIGINT, sigint_handler)
