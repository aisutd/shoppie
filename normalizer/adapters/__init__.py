from normalizer.adapters.bestbuy import BestBuyAdapter
from normalizer.adapters.target import TargetAdapter
from normalizer.adapters.walmart import WalmartAdapter
from normalizer.adapters.amazon import AmazonAdapter


ADAPTERS = {
    "amazon": AmazonAdapter(),
    "target": TargetAdapter(),
    "walmart": WalmartAdapter(),
    "bestbuy": BestBuyAdapter(),
}