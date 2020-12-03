import logging

import numpy as np

from just_bin_it.histograms.input_validators import (
    check_det_range,
    check_int,
    check_tof,
    generate_exception,
)


def _validate_parameters(tof_range, det_range, width, height):
    """
    Checks that the required parameters are defined, if not throw.

    Note: probably not entirely bullet-proof but a good first defence.

    :param tof_range: The time-of-flight range.
    :param det_range: The detector range.
    :param width: The detector width.
    :param height: The detector height.
    """
    missing = []
    invalid = []

    check_tof(tof_range, missing, invalid)
    check_det_range(det_range, missing, invalid)
    check_int(width, "width", invalid)
    check_int(height, "height", invalid)
    if missing or invalid:
        generate_exception(missing, invalid, "2D Map")


class DetHistogram:
    """Two dimensional histogram for detectors."""

    def __init__(
        self, topic, tof_range, det_range, width, height, source="", identifier=""
    ):
        """
        Constructor.

        :param topic: The name of the Kafka topic to publish to.
        :param tof_range: The range of time-of-flights to histogram over [NOT USED].
        :param source: The data source to histogram.
        :param det_range: The range of sequential detectors to histogram over.
        :param width: How many detectors in a row.
        :param height:
        :param identifier: An optional identifier for the histogram.
        """
        _validate_parameters(tof_range, det_range, width, height)
        self._histogram = None
        self.x_edges = None
        self.tof_range = tof_range
        self.det_range = det_range
        # The number of bins is the number of detectors.
        self.num_bins = det_range[1] - det_range[0] + 1
        self.width = width
        self.height = height
        self.topic = topic
        self.last_pulse_time = 0
        self.identifier = identifier
        self.source = source if source.strip() != "" else None

        self._intialise_histogram()

    def _intialise_histogram(self):
        """
        Create a zeroed histogram with the correct shape.
        """
        self._histogram, self.x_edges, self.y_edges = np.histogram2d(
            [],
            [],
            range=((0, self.width), (0, self.height)),
            bins=(self.width, self.height),
        )

    @property
    def data(self):
        return self._histogram

    @property
    def shape(self):
        return self._histogram.shape

    def add_data(self, pulse_time, tof, det_ids, source=""):
        """
        Add data to the histogram.

        :param pulse_time: The pulse time.
        :param tof: The time-of-flight data.
        :param det_ids: The detector data.
        :param source: The source of the event.
        """
        # Discard any messages not from the specified source.
        if self.source is not None and source != self.source:
            return

        self.last_pulse_time = pulse_time

        dets_x = []
        dets_y = []

        for id in det_ids:
            if id <= 0 or id < self.det_range[0] or id > self.det_range[1]:
                continue
            x = (id - 1) % self.width
            y = ((id - 1) // self.width) % self.height
            dets_x.append(x)
            dets_y.append(y)

        self._histogram += np.histogram2d(
            dets_x,
            dets_y,
            range=((0, self.width), (0, self.height)),
            bins=(self.width, self.height),
        )[0]

    def clear_data(self):
        """
        Clears the histogram data, but maintains the other values (e.g. edges etc.)
        """
        logging.info("Clearing data")  # pragma: no mutate
        self._intialise_histogram()