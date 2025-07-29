import toml
import yaml


def read_uv_lock(file_path):
    with open(file_path) as file:
        data = toml.load(file)

    return {p["name"]: p["version"] for p in data["package"]}


def read_environment_frozen(file_path):
    with open(file_path) as file:
        data = yaml.safe_load(file)

    return {
        dependency.split("=")[0]: dependency.split("=")[1]
        for dependency in data["dependencies"]
        if isinstance(dependency, str)
    }


def main():
    uv_lock_data = read_uv_lock("version_info/uv.lock")
    environment_frozen_data = read_environment_frozen(
        "version_info/environment-frozen.yml"
    )

    for k, v in uv_lock_data.items():
        if k not in environment_frozen_data:
            print(f"{k} is not in the environment-frozen.yml file")
        else:
            if v != environment_frozen_data[k]:
                print(f"{k}: {v} vs {environment_frozen_data[k]}")


if __name__ == "__main__":
    main()
