import numpy as np
from fast_histogram import histogram1d
import math


class SingleEventHistogrammer1d:
    """Histograms time-of-flight for the denex detector into a 1-D histogram."""

    def __init__(
        self,
        topic,
        num_bins=50,
        tof_range=None,
        source=None,
        preprocessor=None,
        roi=None,
    ):
        """
        Constructor.

        Note on preprocessing functions: this should used for relatively low impact
        processing, i.e. avoid CPU intense algorithms.

        :param topic: The name of the Kafka topic to publish to.
        :param num_bins: The number of bins to divide the time-of-flight up into.
        :param tof_range: The time-of-flight range to histogram over (nanoseconds).
        :param source: The data source to histogram.
        :param preprocessor: The function to apply to the data before adding.
        :param roi: The function for checking data is within the region of interest.

        """
        self.histogram = None
        self.x_edges = None
        self.tof_range = tof_range
        self.num_bins = num_bins
        self.topic = topic
        self.source = source
        self.preprocessor = preprocessor
        self.roi = roi

        # Create a list of pulse times assuming the first pulse is at 0.00
        # i.e on the second.
        pulse_freq = 14
        self.pulse_times = []
        for i in range(pulse_freq):
            # In nanoseconds
            self.pulse_times.append(math.floor(i / pulse_freq * 10 ** 9))
        self.pulse_times.append(10 ** 9)

    def add_data(self, pulse_time, tofs=None, det_ids=None, source=""):
        """
        Add data to the histogram.

        :param pulse_time: The pulse time which is used as the event time.
        :param tofs: Ignored parameter.
        :param det_ids: An array of one value which is the pixel hit.
        :param source: The source of the event.
        """
        # Discard any messages not from the specified source.
        if self.source is not None and source != self.source:
            return

        # Throw away the seconds part
        nanosecs = pulse_time % 1_000_000_000

        bin_num = np.digitize([nanosecs], self.pulse_times)

        corrected_time = nanosecs - self.pulse_times[bin_num[0] - 1]

        if self.preprocessor is not None:
            pulse_time, tofs, y = self._preprocess_data(pulse_time, tofs, det_ids)

        if self.roi is not None:
            # Mask will contain one value if that is 1 then the value is not added.
            if self._get_mask(pulse_time, tofs, det_ids)[0]:
                return

        if self.histogram is None:
            # Assumes that fast_histogram produces the same bins as numpy.
            self.x_edges = np.histogram_bin_edges(
                [corrected_time], self.num_bins, self.tof_range
            )
            self.histogram = histogram1d(
                [corrected_time], range=self.tof_range, bins=self.num_bins
            )
        else:
            self.histogram += histogram1d(
                [corrected_time], range=self.tof_range, bins=self.num_bins
            )

    def _preprocess_data(self, pulse_time, tof, det_id):
        """
        Apply the defined processing function to the data.

        :param pulse_time: The pulse time which is used as the event time.
        :param tof: Ignored parameter.
        :param det_id: The pixel hit.
        :return: The newly processed data.
        """
        try:
            pulse_time, tof, det_id = self.preprocessor(pulse_time, tof, det_id)
        except Exception:
            # TODO: log
            print("Exception while preprocessing data")
        return pulse_time, tof, det_id

    def _get_mask(self, event_time, tof, det_id):
        """
        Apply the defined processing function to the data.

        1 is used to indicate a masked value.
        0 is used to indicate an unmasked value.

        :param event_time: The pulse time which is used as the event time.
        :param tof: Ignored parameter.
        :param det_id: The pixel hit.
        :return: The newly processed data.
        """
        try:
            mask = self.roi(event_time, tof, det_id)
        except Exception:
            # TODO: log
            print("Exception while try to check ROI")
            mask = None
        return mask
