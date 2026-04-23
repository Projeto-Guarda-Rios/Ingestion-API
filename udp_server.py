from __future__ import annotations

import asyncio
import logging
import signal
from asyncio import DatagramProtocol

from auth import known_station_ids
from config import settings
from ingest import record_batch
from udp_codec import CodecError, decode_packet

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class IngestDatagramProtocol(DatagramProtocol):
    def connection_made(self, transport):
        sockname = transport.get_extra_info("sockname")
        logger.info(
            "udp: listening host=%s port=%s stations=%s",
            sockname[0],
            sockname[1],
            ",".join(sorted(known_station_ids())),
        )

    def datagram_received(self, data: bytes, addr):
        try:
            packet = decode_packet(data)
        except CodecError as exc:
            logger.warning("udp: dropped peer=%s:%s bytes=%d err=%s", addr[0], addr[1], len(data), exc)
            return

        sample_values = ", ".join(
            f"#{index + 1}(temp={reading.temperature:.2f}, turbidity={reading.turbidity:.2f})"
            for index, reading in enumerate(packet.readings)
        )
        logger.info(
            "udp: decoded peer=%s:%s station=%s packet_counter=%d values=[%s]",
            addr[0],
            addr[1],
            packet.station_label,
            packet.packet_counter,
            sample_values,
        )

        try:
            count = record_batch(packet.station_label, packet.readings)
        except Exception:
            logger.exception(
                "udp: influx write failed station=%s packet_counter=%d",
                packet.station_label,
                packet.packet_counter,
            )
            return

        logger.info(
            "udp: ingested peer=%s:%s station=%s station_id=%d packet_counter=%d samples=%d",
            addr[0],
            addr[1],
            packet.station_label,
            packet.station_number,
            packet.packet_counter,
            count,
        )


async def run() -> None:
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    transport, _ = await loop.create_datagram_endpoint(
        IngestDatagramProtocol,
        local_addr=(settings.udp_host, settings.udp_port),
    )
    try:
        await stop_event.wait()
    finally:
        transport.close()
        logger.info("udp: stopped")


if __name__ == "__main__":
    asyncio.run(run())
