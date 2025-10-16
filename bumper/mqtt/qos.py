from enum import Enum

class QoS(Enum):
    QoS0 = 0  # At most once
    QoS1 = 1  # At least once
    QoS2 = 2  # Exactly once