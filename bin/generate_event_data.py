import argparse
import os
import sys
import time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from just_bin_it.endpoints.serialisation import serialise_ev42
from just_bin_it.endpoints.kafka_producer import Producer


LOW_TOF = 0
HIGH_TOF = 100_000_000
LOW_DET = 1
HIGH_DET = 512


def generate_data(source, message_id, num_points):
    tof_centre = (HIGH_TOF - LOW_TOF) // 2
    tof_scale = tof_centre // 5
    det_centre = (HIGH_DET - LOW_DET) // 2
    det_scale = det_centre // 5
    time_stamp = time.time_ns()

    tofs = [int(x) for x in np.random.normal(tof_centre, tof_scale, num_points)]
    dets = [int(x) for x in np.random.normal(det_centre, det_scale, num_points)]
    data = serialise_ev42(source, message_id, time_stamp, tofs, dets)
    return time_stamp, data


def main(brokers, topic, num_msgs, num_points):
    producer = Producer(brokers)
    count = 0
    message_id = 1
    start_time = None
    end_time = None

    while count < num_msgs:
        timestamp, data = generate_data("just-bin-it", message_id, num_points)
        producer.publish_message(topic, data)
        message_id += 1
        count += 1

        if not start_time:
            start_time = timestamp
        end_time = timestamp

        time.sleep(1)


    print(f"Num messages = {num_msgs}, total events = {num_msgs * num_points}")
    print(f"Start timestamp = {start_time}, end_timestamp = {end_time}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    required_args = parser.add_argument_group("required arguments")
    required_args.add_argument(
        "-b",
        "--brokers",
        type=str,
        nargs="+",
        help="the broker addresses",
        required=True,
    )

    required_args.add_argument(
        "-t", "--topic", type=str, help="the topic to write to", required=True
    )

    required_args.add_argument(
        "-n", "--num_messages", type=int, help="the number of messages to write", required=True
    )

    parser.add_argument(
        "-ne",
        "--num_events",
        type=int,
        default=1000,
        help="the number of events per message",
    )

    args = parser.parse_args()

    main(args.brokers, args.topic, args.num_messages, args.num_events)
