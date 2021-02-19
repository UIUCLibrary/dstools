import abc
import os
from typing import Dict, Any, Iterable, List, Optional, Union
import speedwagon


class AbsOptionValidator(abc.ABC):
    @abc.abstractmethod
    def is_valid(self, **user_data: Any) -> bool:
        """Evaluate if the kwargs are valid"""

    @abc.abstractmethod
    def explanation(self, **user_data: Any) -> str:
        """Get reason for is_valid.

        Args:
            **user_data:

        Returns:
            returns a message explaining why something isn't valid, otherwise
                produce the message "ok"
        """


class DirectoryValidation(AbsOptionValidator):

    def __init__(self, key: str) -> None:
        self._key: str = key

    @staticmethod
    def destination_exists(path: str) -> bool:
        return os.path.exists(path)

    def is_valid(self, **user_data: Any) -> bool:
        if self._key not in user_data:
            return False
        output = user_data[self._key]
        if self.destination_exists(output) is False:
            return False
        return True

    def explanation(self, **user_data: Any) -> str:
        destination = user_data.get(self._key)
        if destination is None:
            return f"Missing {self._key}"

        if self.destination_exists(destination) is False:
            return f'Directory "{destination}" does not exist'
        return "ok"


class OptionValidatorFactory:
    def __init__(self) -> None:
        self._validators: Dict[str, AbsOptionValidator] = {}

    def register_validator(self,
                           key: str,
                           validator: AbsOptionValidator) -> None:

        self._validators[key] = validator

    def create(self, key: str) -> AbsOptionValidator:
        builder = self._validators.get(key)
        if not builder:
            raise ValueError(key)
        return builder


class OptionValidator(OptionValidatorFactory):
    def get(self, key: str) -> AbsOptionValidator:
        return self.create(key)


class OptionValidation:

    def get_issues(
            self,
            workflow: speedwagon.Workflow,
            key: str,
            value
    ) -> Iterable[str]:
        return []


class OptionValidationValidKey(OptionValidation):

    def __init__(self, *valid_keys: str) -> None:
        self.keys = valid_keys
        super().__init__()

    def get_issues(
            self,
            workflow: speedwagon.Workflow,
            key: str,
            value: Union[str, bool, None]
    ) -> Iterable[str]:
        valid_keys: Iterable[str] = self.keys or [o.label_text for o in workflow.user_options()]
        if key not in valid_keys:
            yield f'[{key}] is not a valid option'


class OptionValidateDirectory(OptionValidation):

    def __init__(self, *keys: str) -> None:
        """Check if key is in the vaklid keys

        Args:
            *keys:
        """
        super().__init__()
        self.keys = keys

    def get_issues(
            self,
            workflow: speedwagon.Workflow,
            key: str,
            value: Optional[str]
    ) -> Iterable[str]:

        if key not in self.keys:
            return []
        if value is None:
            return [
                f"{key} is empty"
            ]
        if os.path.exists(value) is False:
            yield f'"Directory "{value}" does not exist"'


class OptionValidator2:

    def __init__(self, workflow: speedwagon.Workflow) -> None:
        super().__init__()
        self.workflow = workflow
        self.validators: List[OptionValidation] = []

    def find_user_option_errors(self, key: str, value: Union[str, bool, None]) -> Iterable[str]:
        issues: List[str] = []
        for v in self.validators:
            issues += v.get_issues(workflow=self.workflow, key=key, value=value)
        return list(set(issues))
