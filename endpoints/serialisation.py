import flatbuffers
import numpy as np
from fbschemas.ev42.EventMessage import EventMessage
import fbschemas.hs00.EventHistogram as EventHistogram
import fbschemas.hs00.DimensionMetaData as DimensionMetaData
import fbschemas.hs00.ArrayDouble as ArrayDouble
from fbschemas.hs00.Array import Array


def get_schema(buf):
    """
    Extract the schema code embedded in the buffer

    :param buf: The raw buffer of the FlatBuffers message.
    :return: The schema name
    """
    return buf[4:8].decode("utf-8")


def deserialise_ev42(buf):
    """
    Deserialise an ev42 FlatBuffers message.

    :param buf: The raw buffer of the FlatBuffers message.
    :return: A dictionary of the deserialised values.
    """
    # Check schema is correct
    if get_schema(buf) != "ev42":
        raise Exception(f"Incorrect schema: expected ev42 but got {get_schema(buf)}")

    event = EventMessage.GetRootAsEventMessage(buf, 0)

    data = {
        "message_id": event.MessageId(),
        "pulse_time": event.PulseTime(),
        "source": event.SourceName().decode("utf-8"),
        "det_ids": event.DetectorIdAsNumpy(),
        "tofs": event.TimeOfFlightAsNumpy(),
    }
    return data


def deserialise_hs00(buf):
    """
    Convert flatbuffer into a histogram.

    :param buf:
    :return: dict of histogram information
    """
    # Check schema is correct
    if get_schema(buf) != "hs00":
        raise Exception(f"Incorrect schema: expected hs00 but got {get_schema(buf)}")

    event_hist = EventHistogram.EventHistogram.GetRootAsEventHistogram(buf, 0)

    dims = []
    for i in range(event_hist.DimMetadataLength()):
        bins_fb = event_hist.DimMetadata(i).BinBoundaries()

        # Get bins
        temp = ArrayDouble.ArrayDouble()
        temp.Init(bins_fb.Bytes, bins_fb.Pos)
        bins = temp.ValueAsNumpy()

        # Get type
        if event_hist.DimMetadata(i).BinBoundariesType() == Array.ArrayDouble:
            bin_type = np.float64
        else:
            raise TypeError("Type of the bin boundaries is incorrect")

        hist_info = {
            "length": event_hist.DimMetadata(i).Length(),
            "edges": bins.tolist(),
            "type": bin_type,
        }
        dims.append(hist_info)

    # Get the data
    if event_hist.DataType() != Array.ArrayDouble:
        raise TypeError("Type of the data array is incorrect")  # pragma: no mutate

    data_fb = event_hist.Data()
    temp = ArrayDouble.ArrayDouble()
    temp.Init(data_fb.Bytes, data_fb.Pos)
    data = temp.ValueAsNumpy()
    shape = event_hist.CurrentShapeAsNumpy().tolist()

    hist = {
        "source": event_hist.Source().decode("utf-8"),
        "shape": shape,
        "dims": dims,
        "data": data.reshape(shape),
        "info": event_hist.Info().decode("utf-8") if event_hist.Info() else "",
    }
    return hist


def _serialise_metadata(builder, edges, length):
    ArrayDouble.ArrayDoubleStartValueVector(builder, len(edges))
    # FlatBuffers builds arrays backwards
    for x in reversed(edges):
        builder.PrependFloat64(x)
    bins = builder.EndVector(len(edges))
    # Add the bins
    ArrayDouble.ArrayDoubleStart(builder)
    ArrayDouble.ArrayDoubleAddValue(builder, bins)
    pos_bin = ArrayDouble.ArrayDoubleEnd(builder)

    DimensionMetaData.DimensionMetaDataStart(builder)
    DimensionMetaData.DimensionMetaDataAddLength(builder, length)
    DimensionMetaData.DimensionMetaDataAddBinBoundaries(builder, pos_bin)
    DimensionMetaData.DimensionMetaDataAddBinBoundariesType(builder, Array.ArrayDouble)
    return DimensionMetaData.DimensionMetaDataEnd(builder)


def serialise_hs00(histogrammer, info_message: str = ""):
    """
    Serialise a histogram as an hs00 FlatBuffers message.

    :param histogrammer: The histogrammer containing the histogram to serialise.
    :param info_message: Information to write to the 'info' field.
    :return: The raw buffer of the FlatBuffers message.
    """
    # TODO: provide timestamp?
    file_identifier = b"hs00"

    # histogram = histogrammer.data
    builder = flatbuffers.Builder(1024)
    source = builder.CreateString("just-bin-it")
    info = builder.CreateString(info_message)

    # Build shape array
    rank = len(histogrammer.shape)
    EventHistogram.EventHistogramStartCurrentShapeVector(builder, rank)
    # FlatBuffers builds arrays backwards
    for s in reversed(histogrammer.shape):
        builder.PrependUint32(s)
    shape = builder.EndVector(rank)

    # Build dimensions metadata
    # Build the x bins vector
    metadata = [
        _serialise_metadata(builder, histogrammer.x_edges, histogrammer.shape[0])
    ]

    # Build the y bins vector, if present
    if hasattr(histogrammer, "y_edges"):
        metadata.append(
            _serialise_metadata(builder, histogrammer.y_edges, histogrammer.shape[1])
        )

    EventHistogram.EventHistogramStartDimMetadataVector(builder, rank)
    # FlatBuffers builds arrays backwards
    for m in reversed(metadata):
        builder.PrependUOffsetTRelative(m)
    metadata_vector = builder.EndVector(rank)

    # Build the data
    data_len = len(histogrammer.data)
    if len(histogrammer.shape) == 2:
        # 2-D data will be flattened into one array
        data_len = histogrammer.shape[0] * histogrammer.shape[1]

    ArrayDouble.ArrayDoubleStartValueVector(builder, data_len)
    # FlatBuffers builds arrays backwards
    for x in reversed(histogrammer.data.flatten()):
        builder.PrependFloat64(x)
    data = builder.EndVector(data_len)
    ArrayDouble.ArrayDoubleStart(builder)
    ArrayDouble.ArrayDoubleAddValue(builder, data)
    pos_data = ArrayDouble.ArrayDoubleEnd(builder)

    # Build the actual buffer
    EventHistogram.EventHistogramStart(builder)
    EventHistogram.EventHistogramAddSource(builder, source)
    EventHistogram.EventHistogramAddInfo(builder, info)
    EventHistogram.EventHistogramAddCurrentShape(builder, shape)
    EventHistogram.EventHistogramAddDimMetadata(builder, metadata_vector)
    EventHistogram.EventHistogramAddData(builder, pos_data)
    EventHistogram.EventHistogramAddDataType(builder, Array.ArrayDouble)
    hist = EventHistogram.EventHistogramEnd(builder)
    builder.Finish(hist)

    # Generate the output and replace the file_identifier
    buff = builder.Output()
    buff[4:8] = file_identifier
    return buff
