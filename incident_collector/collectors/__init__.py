from incident_collector.collectors.defihacklabs import DeFiHackLabsCollector
from incident_collector.collectors.notion_web3sec import Web3SecNotionCollector
from incident_collector.collectors.slowmist import SlowMistCollector

COLLECTOR_REGISTRY = {
    "slowmist": SlowMistCollector,
    "defihacklabs": DeFiHackLabsCollector,
    "web3sec": Web3SecNotionCollector,
}
