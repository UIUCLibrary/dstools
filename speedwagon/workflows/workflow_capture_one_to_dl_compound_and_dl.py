"""Workflow for converting Capture One tiff file into two formats."""
# pylint: disable=unsubscriptable-object
from __future__ import annotations
import logging
import os

from typing import List, Any, Dict, Callable, Iterator, Union, Iterable, \
    Optional
from contextlib import contextmanager
from uiucprescon import packager
from uiucprescon.packager.packages.abs_package_builder import AbsPackageBuilder
from uiucprescon.packager.packages.collection_builder import Metadata
from uiucprescon.packager.packages.collection import AbsPackageComponent
from speedwagon import tasks, Workflow
from speedwagon.workflows import shared_custom_widgets as options
from speedwagon.worker import GuiLogHandler
import speedwagon.validators


class CaptureOneToDlCompoundAndDLWorkflow(Workflow):
    """Settings for convert capture one tiff files."""

    name = "Convert CaptureOne TIFF to Digital Library Compound Object and " \
           "HathiTrust"
    description = "Input is a path to a folder of TIFF files all named with " \
                  "a bibid as a prefacing identifier, a final delimiting " \
                  "dash, and a sequence consisting of " \
                  "padded zeroes and a number." \
                  "\n" \
                  "Output Hathi is a directory to put the new packages for " \
                  "HathiTrust."
    active = True

    def user_options(self) -> List[options.UserOptionCustomDataType]:
        """Get the options types need to configuring the workflow.

        Returns:
            Returns a list of user option types

        """
        return [
            options.UserOptionCustomDataType("Input", options.FolderData),
            options.UserOptionCustomDataType(
                "Output Digital Library", options.FolderData),
            options.UserOptionCustomDataType(
                "Output HathiTrust", options.FolderData),
                ]

    def discover_task_metadata(
            self,
            initial_results: List[Any],
            additional_data: Dict[str, str],
            **user_args: str
    ) -> List[Dict[str, Union[str, AbsPackageComponent]]]:
        """Look at user settings and discover any data needed to build a task.

        Args:
            initial_results:
            additional_data:
            **user_args:

        Returns:
            Returns a list of data to create a job with

        """
        jobs: List[Dict[str, Union[str, AbsPackageComponent]]] = []

        source_input = user_args["Input"]
        dest_dl = user_args["Output Digital Library"]
        dest_ht = user_args["Output HathiTrust"]

        package_factory = packager.PackageFactory(
            packager.packages.CaptureOnePackage(delimiter="-"))
        for package in package_factory.locate_packages(source_input):
            new_job: Dict[str,
                          Union[str, AbsPackageComponent, Dict[str, str]]] = {
                "package": package,
                "source_path": source_input
            }
            output: Dict[str, str] = {}

            if dest_ht is not None and dest_ht.strip() != "":
                output["hathi_trust"] = dest_ht

            if dest_dl is not None and dest_dl.strip() != "":
                output["digital_library"] = dest_dl

            new_job["outputs"] = output
            jobs.append(new_job)
        return jobs

    @staticmethod
    def validate_user_options(**user_args: Optional[str]) -> bool:
        """Validate the user's arguments.

        Raises a value error is something is not valid.

        Args:
            **user_args:

        """
        invalid_messages = []

        all_options_validator = speedwagon.validators.OptionValidator2(
            CaptureOneToDlCompoundAndDLWorkflow()
        )
        all_options_validator.validators += [
            speedwagon.validators.OptionValidationValidKey(),
            speedwagon.validators.OptionValidateDirectory("Input"),
            AtLeastOneOutput(
                "Output Digital Library",
                "Output HathiTrust",
                user_args=user_args
            )
        ]

        for option, user_input in user_args.items():
            for issue in \
                    all_options_validator.find_user_option_errors(
                        key=option,
                        value=user_input):

                invalid_messages.append(issue)

        if len(invalid_messages) > 0:
            raise ValueError("\n".join(invalid_messages))
        return True

    def create_new_task(
            self,
            task_builder: tasks.TaskBuilder,
            **job_args
    ) -> None:
        """Generate a new task.

        Args:
            task_builder:
            **job_args:

        """
        existing_package: AbsPackageComponent = job_args['package']
        source_path: str = str(job_args["source_path"])
        package_id: str = existing_package.metadata[Metadata.ID]
        for new_task in self.create_package_tasks(
                existing_package=existing_package,
                outputs=job_args['outputs'],
                package_id=package_id,
                source_path=source_path):
            task_builder.add_subtask(new_task)

    @staticmethod
    def create_package_tasks(
            existing_package: AbsPackageComponent,
            outputs: Dict[str, str],
            package_id: str,
            source_path: str
    ) -> Iterable[PackageConverter]:

        new_dl_package_root: Optional[str] = outputs.get('digital_library')
        if new_dl_package_root:
            yield PackageConverter(
                source_path=source_path,
                existing_package=existing_package,
                new_package_root=new_dl_package_root,
                packaging_id=package_id,
                package_format="Digital Library Compound",

            )

        new_ht_package_root: Optional[str] = outputs.get('hathi_trust')
        if new_ht_package_root:
            yield PackageConverter(
                source_path=source_path,
                existing_package=existing_package,
                new_package_root=new_ht_package_root,
                packaging_id=package_id,
                package_format="HathiTrust jp2",
            )


class PackageConverter(tasks.Subtask):
    """Convert packages formats."""

    name = "Package Conversion"
    package_formats: Dict[str, AbsPackageBuilder] = {
        "Digital Library Compound": packager.packages.DigitalLibraryCompound(),
        "HathiTrust jp2": packager.packages.HathiJp2()
    }

    @contextmanager
    def log_config(self, logger: logging.Logger) -> Iterator[None]:
        """Configure logs so they get forwarded to the speedwagon console.

        Args:
            logger:

        """
        gui_logger = GuiLogHandler(self.log)
        try:
            logger.addHandler(gui_logger)
            yield
        finally:
            logger.removeHandler(gui_logger)

    def __init__(self,
                 source_path: str,
                 packaging_id: str,
                 existing_package: AbsPackageComponent,
                 new_package_root: str,
                 package_format: str) -> None:
        """Create PackageConverter object.

        Args:
            source_path:
            packaging_id:
            existing_package:
            new_package_root:
            package_format:
        """
        super().__init__()
        self.package_factory: \
            Callable[[AbsPackageBuilder], packager.PackageFactory] \
            = packager.PackageFactory

        self.packaging_id = packaging_id
        self.existing_package = existing_package
        self.new_package_root = new_package_root
        if package_format not in PackageConverter.package_formats.keys():
            raise ValueError(f"{package_format} is not a known value")
        self.package_format = package_format
        self.source_path = source_path

    def work(self) -> bool:
        """Convert source package to the new type.

        Returns:
            True on success, False on failure

        """
        my_logger = logging.getLogger(packager.__name__)
        my_logger.setLevel(logging.INFO)
        with self.log_config(my_logger):
            self.log(
                f"Converting {self.packaging_id} from {self.source_path} "
                f"to a {self.package_format} package at "
                f"{self.new_package_root}")

            package_factory = self.package_factory(
                PackageConverter.package_formats[self.package_format]
            )

            package_factory.transform(
                self.existing_package, dest=self.new_package_root)
        return True


class AtLeastOneOutput(speedwagon.validators.OptionValidation):
    def __init__(
            self, *keys: str, user_args: Dict[str, Optional[Any]]
    ) -> None:
        self.keys = keys
        self.user_args = user_args

    def get_issues(self, workflow: speedwagon.Workflow, key: str,
                   value: Optional[str]) -> Iterable[str]:

        if key not in self.keys:
            return []

        if self.is_valid_value(value):
            return []

        if value is not None and value != "" and not os.path.exists(value):
            yield f"Directory \"{value}\" does not exist"

        if not self.at_least_one_output_is_valid():
            yield f"At least one of the follow options must be a valid " \
                  f"directory {self.keys}"

    def at_least_one_output_is_valid(self) -> bool:
        user_args = self.user_args

        other_outputs: List[str] = []
        for k in self.keys:
            arg = user_args.get(k)
            if arg:
                other_outputs.append(arg)

        return any([self.is_valid_value(a) for a in other_outputs])

    @staticmethod
    def is_valid_value(value: Optional[str]) -> bool:

        if value is None:
            return False

        if value == "":
            return False

        return os.path.exists(value)
