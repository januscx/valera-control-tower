from pathlib import Path

from setuptools import find_packages, setup


PACKAGE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = PACKAGE_DIR.parents[1]
ROBOT_PACKAGES = find_packages(
    where=str(REPOSITORY_ROOT),
    include=("robot", "robot.*"),
)

setup(
    name="valera_vr_gateway",
    version="0.1.0",
    packages=ROBOT_PACKAGES,
    package_dir={
        package: str(REPOSITORY_ROOT / package.replace(".", "/"))
        for package in ROBOT_PACKAGES
    },
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/valera_vr_gateway"],
        ),
        ("share/valera_vr_gateway", ["package.xml"]),
        (
            "share/valera_vr_gateway/launch",
            [str(path.relative_to(PACKAGE_DIR)) for path in (PACKAGE_DIR / "launch").glob("*.launch.py")],
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    entry_points={
        "console_scripts": [
            "valera_vr_gateway_node = robot.vr_gateway_ros.node:main",
        ],
    },
)
