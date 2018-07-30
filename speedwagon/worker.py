import concurrent.futures
import traceback

# from abc import ABCMeta, abstractmethod
import contextlib
import logging
import queue
import typing
import abc
import sys
from PyQt5 import QtCore, QtWidgets
from collections import namedtuple
import multiprocessing
from .tasks import AbsSubtask, QueueAdapter

MessageLog = namedtuple("MessageLog", ("message",))


class QtMeta(type(QtCore.QObject), abc.ABCMeta):  # type: ignore
    pass


class NoWorkError(RuntimeError):
    pass


class AbsJobWorker(metaclass=QtMeta):
    name: typing.Optional[str] = None

    def __init__(self):
        self.result = None
        self.successful = None

    def execute(self, *args, **kwargs):
        try:
            self.process(*args, **kwargs)
            self.on_completion(*args, **kwargs)
            self.successful = True
            return self.result
        except Exception as e:
            print("Failed {}".format(e), file=sys.stderr)
            self.successful = False
            raise

    @abc.abstractmethod
    def process(self, *args, **kwargs):
        pass

    @abc.abstractmethod
    def log(self, message):
        pass

    def on_completion(self, *args, **kwargs):
        pass

    @classmethod
    def new(cls, job, message_queue, *args, **kwargs):
        new_job = job()
        new_job.set_message_queue(message_queue)
        new_job.execute(*args, **kwargs)
        return new_job.task_result
        # print(logger_queue)
        # print(task)
        # print("HERER")


class ProcessJobWorker(AbsJobWorker):
    _mq = None

    def __init__(self):
        super().__init__()

    #     # self._mq = None

    def process(self, *args, **kwargs):
        pass

    def set_message_queue(self, value):
        pass
        self._mq = value
        # cls.mq = value

    def log(self, message):
        if self._mq:
            self._mq.put(message)


class JobPair(typing.NamedTuple):
    task: ProcessJobWorker
    args: dict


class WorkerMeta(type(QtCore.QObject), abc.ABCMeta):  # type: ignore
    pass


class Worker2(metaclass=abc.ABCMeta):
    @classmethod
    @abc.abstractmethod
    def initialize_worker(cls) -> None:
        """Initialize the executor"""
        pass


class Worker(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def initialize_worker(self) -> None:
        """Initialize the executor"""
        pass

    @abc.abstractmethod
    def cancel(self) -> None:
        """Shutdown the executor"""
        pass

    @abc.abstractmethod
    def run_all_jobs(self):
        """Execute jobs in loaded in q"""
        pass

    @abc.abstractmethod
    def add_job(self, job: typing.Type[ProcessJobWorker], **job_args):
        """Load jobs into queue"""
        pass


class UIWorker(Worker):
    # class Worker(QtCore.QObject, metaclass=WorkerMeta):
    def __init__(self, parent):
        """Interface for managing jobs. Designed handle loading and executing jobs.

        Args:
            parent: The widget controlling the worker
        """
        super().__init__()
        self.parent = parent
        self._jobs_queue = queue.Queue()


# class ProcessWorker(Worker):
class ProcessWorker(UIWorker, QtCore.QObject, metaclass=WorkerMeta):
    # _message_queue = manager.Queue(maxsize=100)
    # _message_queue = queue.Queue()  # type: ignore
    executor = concurrent.futures.ProcessPoolExecutor(max_workers=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.manager = multiprocessing.Manager()
        self._message_queue = self.manager.Queue()  # type: ignore
        self._results = None
        # self.manager = multiprocessing.Manager()
        self._tasks = []
        # self.executor = None
        # self._message_queue = self.manager.Queue(maxsize=1)

    @classmethod
    def initialize_worker(cls, max_workers=1):

        cls.executor = concurrent.futures.ProcessPoolExecutor(
            max_workers=max_workers
        )  # TODO: Fix this

    def cancel(self):
        # if hasattr(self, "executor"):
        self.executor.shutdown()

    @classmethod
    def _exec_job(cls, job, args, message_queue):
        new_job = job()
        # new_job.set_message_queue(logger_queue)
        new_job.mq = message_queue
        fut = cls.executor.submit(new_job.execute, **args)

        # fut.add_done_callback(self.complete_task)
        return fut

    def add_job(self, job: ProcessJobWorker, **job_args):
        new_job = JobPair(job, args=job_args)
        self._jobs_queue.put(new_job)

    def run_all_jobs(self):

        while self._jobs_queue.qsize() != 0:
            job_, args, message_queue = self._jobs_queue.get()
            fut = self._exec_job(job_, args, message_queue)
            self._tasks.append(fut)
        # logging.debug("All jobs have been launched")
        for future in concurrent.futures.as_completed(self._tasks):
            # logging.debug("future finished")
            self.complete_task(future)
        self.on_completion(results=self._results)

    @abc.abstractmethod
    def complete_task(self, fut: concurrent.futures.Future):
        pass

    @abc.abstractmethod
    def on_completion(self, *args, **kwargs):
        pass


class WorkProgressBar(QtWidgets.QProgressDialog):

    def closeEvent(self, QCloseEvent):
        super().closeEvent(QCloseEvent)

    def __init__(self, *__args):
        super().__init__(*__args)


class ProgressMessageBoxLogHandler(logging.Handler):

    def __init__(self, dialog_box: QtWidgets.QProgressDialog,
                 level=logging.NOTSET) -> None:

        super().__init__(level)
        self.dialog_box = dialog_box

    def emit(self, record):
        try:
            self.dialog_box.setLabelText(record.msg)
        except RuntimeError as e:
            print(record.msg, file=sys.stderr)
            traceback.print_tb(e.__traceback__)


class AbsObserver(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def emit(self, value):
        pass


class AbsSubject(metaclass=abc.ABCMeta):
    lock = multiprocessing.Lock()
    _observers = set()  # type: typing.Set[AbsObserver]

    def subscribe(self, observer: AbsObserver):
        if not isinstance(observer, AbsObserver):
            raise TypeError("Observer not derived from AbsObserver")
        self._observers |= {observer}

    def unsubscribe(self, observer: AbsObserver):
        self._observers -= {observer}

    def notify(self, value=None):
        with self.lock:
            for observer in self._observers:
                if value is None:
                    observer.emit()
                else:
                    observer.emit(value)


class GuiLogHandler(logging.Handler):
    def __init__(self, callback, level=logging.NOTSET):
        super().__init__(level)
        self.callback = callback

    def emit(self, record):
        self.callback(record.msg)


class WorkRunnerExternal2(contextlib.AbstractContextManager):
    def __init__(self, tool, options, parent):
        self.results = []
        self._tool = tool
        self._options = options
        self._parent = parent
        self.abort_callback = None
        # self.jobs: queue.Queue[JobPair] = queue.Queue()

    def __enter__(self):
        self.dialog = QtWidgets.QProgressDialog(self._parent)
        self.dialog.setModal(True)
        self.dialog.setLabelText("Initializing")
        self.dialog.setWindowTitle(self._tool.name)

        self.progress_dialog_box_handler = \
            ProgressMessageBoxLogHandler(self.dialog)

        self.dialog.canceled.connect(self.abort)
        return self

    def abort(self):
        if self.dialog.result() == self.dialog.Accepted:
            print("SUCCESS")
        else:
            if self.abort_callback is not None:
                self.abort_callback()

    def __exit__(self, exc_type, exc_value, traceback):
        self.dialog.hide()


class WorkRunnerExternal3(contextlib.AbstractContextManager):
    def __init__(self, parent):
        self.results = []
        # self._tool = tool
        # self._options = options
        self._parent = parent
        self.abort_callback = None
        self.was_aborted = False
        # self.jobs: queue.Queue[JobPair] = queue.Queue()

    def __enter__(self):
        self.dialog = QtWidgets.QProgressDialog(self._parent)
        self.dialog.setModal(True)
        self.dialog.setLabelText("Initializing")
        self.dialog.setMinimumDuration(100)
        # self.dialog.setWindowTitle("Running")

        self.progress_dialog_box_handler = \
            ProgressMessageBoxLogHandler(self.dialog)

        self.dialog.canceled.connect(self.abort)
        return self

    def abort(self):
        if self.dialog.result() == QtWidgets.QProgressDialog.Rejected:
            self.was_aborted = True
            if self.abort_callback is not None:
                self.abort_callback()

    def __exit__(self, exc_type, exc_value, traceback):
        self.dialog.close()

#
# def _execute(job, **settings):
#     pass


class AbsJobManager(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def add_job(self, new_job, settings):
        pass

    @abc.abstractmethod
    def start(self):
        pass

    @abc.abstractmethod
    def flush_message_buffer(self):
        pass

    @abc.abstractmethod
    def abort(self):
        pass


class ToolJobManager(contextlib.AbstractContextManager, AbsJobManager):

    def __init__(self, max_workers=1) -> None:
        self.manager = multiprocessing.Manager()
        self._max_workers = max_workers
        self.active = False
        self._pending_jobs: queue.Queue[JobPair] = queue.Queue()
        self.futures: typing.List[concurrent.futures.Future] = []
        self.logger = logging.getLogger(__name__)

    def __enter__(self):
        self._message_queue = self.manager.Queue()

        self._executor = concurrent.futures.ProcessPoolExecutor(
            self._max_workers
        )

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        print("Cleaning up")
        self._cleanup()
        print("Shutting down")
        self._executor.shutdown()

    def open(self, parent, runner=WorkRunnerExternal2, *args, **kwargs):
        return runner(*args, **kwargs, parent=parent)

    def add_job(self, new_job: ProcessJobWorker, settings: dict) -> None:

        self._pending_jobs.put(JobPair(new_job, settings))

    def start(self):
        self.active = True
        while not self._pending_jobs.empty():
            job_, settings = self._pending_jobs.get()
            job_.set_message_queue(self._message_queue)
            fut = self._executor.submit(job_.execute, **settings)

            fut.add_done_callback(fn=lambda x: self._pending_jobs.task_done())
            self.futures.append(fut)

    def abort(self):
        self.active = False
        still_running = []

        dialog = QtWidgets.QProgressDialog("Canceling", None, 0, 0)
        dialog.setModal(True)

        # while not self._pending_jobs.empty():
        #     self._pending_jobs.task_done()

        for future in reversed(self.futures):
            if not future.cancel():
                if future.running():
                    still_running.append(future)
            self.futures.remove(future)

        dialog.setRange(0, len(still_running))
        dialog.setLabelText("Please wait")
        dialog.show()
        # TODO: set cancel dialog to force the cancellation of the future

        while True:

            try:
                QtWidgets.QApplication.processEvents()

                futures = concurrent.futures.as_completed(still_running,
                                                          timeout=.1)

                for i, future in enumerate(futures):
                    dialog.setValue(i + 1)

                break
            except concurrent.futures.TimeoutError:
                continue

        self.logger.info("Cancelled")
        self.flush_message_buffer()
        dialog.accept()

    # TODO: refactor to use an overloaded method instead of a callback
    def get_results(self, timeout_callback=None):
        total_jobs = len(self.futures)
        completed = 0
        while self.active:
            try:
                for f in concurrent.futures.as_completed(self.futures,
                                                         timeout=0.01):

                    if not f.cancelled():
                        result = f.result()
                        if f in self.futures:
                            self.futures.remove(f)
                        completed += 1

                        self.flush_message_buffer()
                        if timeout_callback:
                            timeout_callback(completed, total_jobs)
                        if result is not None:
                            yield result

                if timeout_callback:
                    timeout_callback(completed, total_jobs)

                self.active = False
                self.futures.clear()
                # self._pending_jobs.join()
                self.flush_message_buffer()

            except concurrent.futures.TimeoutError:
                self.flush_message_buffer()
                if timeout_callback:
                    # completed = [f for f in self.futures if f.done()]
                    timeout_callback(completed, total_jobs)
                QtWidgets.QApplication.processEvents()
                if self.active:
                    continue
        self.flush_message_buffer()
        # return results

    def flush_message_buffer(self):
        while not self._message_queue.empty():
            self.logger.info(self._message_queue.get())
            self._message_queue.task_done()

    def _cleanup(self):
        if self._pending_jobs.unfinished_tasks > 0:
            self.logger.warning("Pending jobs has unfinished tasks")
        self._pending_jobs.join()


class AbsJobAdapter(metaclass=abc.ABCMeta):
    def __init__(self, adaptee):
        self._adaptee = adaptee

    @property
    def adaptee(self):
        return self._adaptee

    @abc.abstractmethod
    def process(self, *args, **kwargs):
        pass

    @abc.abstractmethod
    def set_message_queue(self, value):
        pass

    @property
    @abc.abstractmethod
    def name(self) -> str:
        pass


class SubtaskJobAdapter(AbsJobAdapter,  # type: ignore
                        ProcessJobWorker):

    def __init__(self, adaptee: AbsSubtask) -> None:
        AbsJobAdapter.__init__(self, adaptee)
        ProcessJobWorker.__init__(self)
        self.adaptee.parent_task_log_q = QueueAdapter()

    @property
    def queue_adapter(self):
        return QueueAdapter()

    def process(self, *args, **kwargs):
        self.adaptee.exec()
        self.result = self.adaptee.task_result

    def set_message_queue(self, value):
        self.adaptee.parent_task_log_q.set_message_queue(value)

    @property
    def settings(self) -> dict:
        if self.adaptee.settings:
            return self.adaptee.settings
        else:
            return {key: value for key, value in self.adaptee.__dict__.items()
                    if key != "parent_task_log_q"}

    @property
    def name(self) -> str:  # type: ignore
        return self.adaptee.name
