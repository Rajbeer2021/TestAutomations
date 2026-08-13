class Namespace:
    """Converts nested dicts into attribute-style objects."""
    def __init__(self, data: dict):
        for key, value in data.items():
            if isinstance(value, dict):
                setattr(self, key, Namespace(value))
            else:
                setattr(self, key, value)

    def __repr__(self):
        return str(self.__dict__)



class ConfigManager:
    def __init__(self, config_dict: dict):
        self.raw = config_dict

        # Convert full config to attribute-accessible object
        for key, value in config_dict.items():
            if isinstance(value, dict):
                setattr(self, key, Namespace(value))
            else:
                setattr(self, key, value)

        # Convert environments to Namespace objects
        self.environments = Namespace({
            env: Namespace(cfg)
            for env, cfg in config_dict["environments"].items()
        })

        # Set active environment (cfg.env)
        self.active_env_name = config_dict["default"]
        self.env = getattr(self.environments, self.active_env_name)

        # Bind direct env access → cfg.dev, cfg.stage, cfg.qa
        for env_name in config_dict["environments"].keys():
            setattr(self, env_name, getattr(self.environments, env_name))

    def set_env(self, env_name: str):
        """Switch active environment dynamically."""
        if not hasattr(self.environments, env_name):
            raise ValueError(f"Environment '{env_name}' not found!")

        self.active_env_name = env_name
        self.env = getattr(self.environments, env_name)

