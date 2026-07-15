from abc import ABC, abstractmethod


class ExecutionAdapter(ABC):
    @abstractmethod
    def accept(self, db, ticket): ...
    @abstractmethod
    def record_exit(self, db, ticket, fill): ...

