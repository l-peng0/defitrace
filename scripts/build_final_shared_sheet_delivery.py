from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import requests


ROOT = Path("/Users/lauren/Desktop/2026spring/capstone")
INTERMEDIATE = ROOT / "output" / "intermediate"
FINAL_OUTPUT = ROOT / "output" / "final"
WEB3SEC_PM_VIEW = "https://web3sec.notion.site/c582b99cd7a84be48d972ca2126a2a1f?v=4671590619bd4b2ab16a15256e4fbba1"
WEB3SEC_BASE = "https://web3sec.notion.site/c582b99cd7a84be48d972ca2126a2a1f"


FINAL_HEADERS = [
    "time (format: yyyy-mm-dd)",
    "data resouce (all resources you referenced)",
    "blockchain platform",
    "attack transaction (via explorer link, we suggest https://app.external_explorer.com/external_explorer/explorer/)",
    "attack contract address (via explorer link)",
    "victim contract address (via explorer link)",
    "note (you can give note for special cases, or just copy report content)",
]


ALIASES = {
    "unverifiedcontracts": "compoundfork",
}

CHAIN_MAP = {
    "etherscan.io": "Ethereum",
    "bscscan.com": "BSC",
    "arbiscan.io": "Arbitrum",
    "basescan.org": "Base",
    "optimistic.etherscan.io": "Optimism",
}

EXTERNAL_EXPLORER_CHAIN_MAP = {
    "Ethereum": "eth",
    "BSC": "bsc",
    "Arbitrum": "arbitrum",
    "Base": "base",
    "Optimism": "optimism",
}


MANUAL_ENRICHMENTS = {
    "caterpillercoin": {
        "extra_sources": [
            "https://www.certik.com/zh-CN/resources/blog/caterpillar-coin-cut-token-incident-analysis",
        ],
    },
    "hydt": {
        "extra_sources": [
            "https://x.com/TenArmorAlert/status/1844241843518951451",
            "https://learnblockchain.cn/article/13124",
        ],
        "attack_contract": "https://bscscan.com/address/0x8f921e27e3af106015d1c3a244ec4f48dbfcad14",
        "victim_contract": "https://bscscan.com/address/0xA2268Fcc2FE7A2Bb755FbE5A7B3Ac346ddFeDB9B",
    },
    "sashatoken": {
        "victim_contract": "https://etherscan.io/address/0xB23FC1241e1Bc1a5542a438775809d38099838fe",
    },
    "p719token": {
        "extra_sources": [
            "https://x.com/TenArmorAlert/status/1844929489823989953",
        ],
    },
    "veth": {
        "poc_url": "https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2024-11/vETH_exp.sol",
        "chain": "Ethereum",
        "extra_sources": [
            "https://blog.verichains.io/p/veth-incident-with-unknown-mechanism",
            "https://x.com/TenArmorAlert/status/1856984299905716645",
            "https://www.quillaudits.com/blog/hack-analysis/veth-token-450k-exploit-analysis",
        ],
    },
    "ast": {
        "extra_sources": [
            "https://blog.solidityscan.com/ast-token-hack-analysis-7a2f0400436a",
            "https://medium.com/@joichiro.sai/ast-token-hack-how-a-faulty-transfer-logic-led-to-a-65k-exploit-da75aed59a43",
        ],
    },
    "bgm": {
        "extra_sources": [
            "https://quadrigainitiative.com/casestudy/bgmonbscbatchtransactionspricemanipulationexploit.php",
        ],
        "attack_contract": "https://bscscan.com/address/0x00c0F54D8Afc60F3aCd06E476Cf504A6f7f06180",
        "victim_contract": "https://bscscan.com/address/0x42646478b25317160e0dc8db413991277e4bb3c2",
    },
    "fortunewheel": {
        "extra_sources": [
            "https://olympixai.medium.com/zoth-fortunewheel-and-sorra-finance-exploited-for-347k-via-ltv-mismatch-unprotected-swaps-and-5fd8ea76a914",
            "https://medium.com/%40victorokubule/flash-loan-exploits-in-defi-the-mechanics-and-prime-workings-of-a-sophisticated-attack-and-exploit-16c73499ddbf",
        ],
        "attack_contract": "https://bscscan.com/address/0x818cd70be0c9dec3b0bc52efaaceb06469ce587f",
        "victim_contract": "https://bscscan.com/address/0x384b9fb6e42dab87f3023d87ea1575499a69998e",
    },
    "harrypotterobamasonic10inu": {
        "extra_sources": [
            "https://quadrigainitiative.com/casestudy/harrypotterobamasonic10inuliquidityaccessvulnerability.php",
            "https://www.gate.com/tr/learn/articles/gate-research-security-incident-summary-for-december-2024/5506",
            "https://cryptonews.net/news/security/30245396/",
        ],
        "attack_tx": "https://etherscan.io/tx/0xb80964b966ec590038b10e1b2c7a4ecb7e75c66f1377c7f0ef78423123dfe0cd",
        "attack_contract": "https://etherscan.io/address/0x8Ca0392D4997C35FA6dDA2c0b6b8314987FAB554",
        "victim_contract": "https://etherscan.io/address/0x553513177faC7142C0F445D721ca7EB22d4215AD",
    },
    "paribus": {
        "extra_sources": [
            "https://bitfinding.com/blog/paribus-hack-interception",
            "https://x.com/BitFinding/status/1882880682512527516",
        ],
        "attack_contract": "https://arbiscan.io/address/0xd368cca925bb3dbadd06ea1b81e96a2174830978",
    },
}


NOTE_OVERRIDES = {
    "caterpillercoin": (
        "An estimated loss of ~1.4M USD was caused by a price-manipulation attack against the CUT token ecosystem on BSC. "
        "The root cause was flawed token economics around reserves and burn logic, which allowed the attacker to distort "
        "the effective pool state and push the token price to an abnormal level.\n\n"
        "The attacker used borrowed liquidity, interacted with the CUT contracts, triggered the vulnerable burn path, "
        "and exited back into BUSD at the manipulated price."
    ),
    "bedrockdefi": (
        "An estimated loss of ~1.7M USD was caused by a price-manipulation issue in BedRock's mint flow. "
        "The PoC shows that the vulnerable vault let the attacker mint uniBTC with ETH under an unsafe pricing assumption, "
        "treating the deposited value too favorably.\n\n"
        "In this incident, the attacker first obtained funding, minted uniBTC through the vulnerable vault, and then "
        "used the mispriced output to swap back into WETH for profit."
    ),
    "firetoken": (
        "An estimated loss of 8.45 ETH (~$20K USD) was caused by a faulty transfer path in the FIRE token contract. "
        "The linked PoC points to the `_transfer()` logic, which allowed the attacker to manipulate the pair balance and "
        "compute an inflated amount of WETH out.\n\n"
        "In this incident, the attacker repeatedly bought FIRE with flash-loaned WETH, transferred FIRE directly into "
        "the WETH/FIRE pair, and then swapped against the distorted reserves to extract WETH."
    ),
    "lavalending": (
        "An estimated loss of about $130K was caused by a price-manipulation attack against LavaLending on Arbitrum. "
        "The PoC shows the attacker cycling through withdrawals, pool interactions, and multiple borrow operations after "
        "distorting the relevant pricing path used by the lending system.\n\n"
        "In this incident, the attacker manipulated the WETH/USDC pricing environment around the lending markets, "
        "inflated the value of the affected position, and then borrowed out USDC, cUSDC, WBTC, and WETH."
    ),
    "aizptoken": (
        "An estimated loss of 34.88 BNB (~$20K USD) was caused by a price-manipulation flaw in the AIZPT token flow. "
        "The PoC shows the attacker flash-borrowing WBNB, sending value into the token contract, and repeatedly "
        "transferring AIZPT back to the token contract to abuse its internal accounting.\n\n"
        "In this incident, the attacker used 8,000 WBNB of temporary liquidity, looped nearly 200 self-transfers, "
        "and then converted the manipulated state back into WBNB for profit."
    ),
    "sashatoken": (
        "An estimated loss of ~249 ETH (~$600K USD) was caused by a price-manipulation attack spanning thin SASHA "
        "liquidity on Ethereum. The PoC shows the attacker buying SASHA with WETH, transferring SASHA into the "
        "Uniswap V2 pair, and then dumping through Uniswap V3 after the price had been distorted.\n\n"
        "In this incident, the attacker used a small initial amount of ETH to push the token into an abnormal pricing "
        "state and then extracted WETH from the manipulated market."
    ),
    "p719token": (
        "An estimated loss of 547.18 BNB (~$312K USD) was caused by a bug in the P719 `transfer()` logic. "
        "According to the linked source notes, sending tokens back to P719 was treated like a sell, and the contract's "
        "burn-and-fee behavior incorrectly inflated the token price.\n\n"
        "In this incident, the attacker created an auxiliary token and pair, split the operation across many helper "
        "contracts, repeatedly bought and sold P719, and then exited after the manipulated price had been amplified."
    ),
    "compoundfork": (
        "An estimated loss of about $1M was caused by price manipulation against an unverified Compound-like lending "
        "deployment on Base. The linked sources describe an excessive-borrowing scenario after the attacker distorted "
        "the asset valuation used by the lending market.\n\n"
        "In this incident, the attacker manipulated the price dependency in the market, used the inflated collateral "
        "state to borrow out assets, and then realized the profit through the mispriced lending contracts."
    ),
    "deltaprime": (
        "An estimated loss of $4.75M was caused by a price-manipulation and reentry-style attack against Delta Prime on "
        "Arbitrum. The PoC shows the attacker creating a SmartLoan position, feeding crafted price data into the loan "
        "flow, and abusing reward-claim execution to reenter at a favorable moment.\n\n"
        "In this incident, the attacker borrowed against a manipulated state, converted collateral and debt positions "
        "through the crafted flow, and exited after the protocol's solvency assumptions had been broken."
    ),
    "veth": (
        "An estimated loss of about $447K was caused by a price-manipulation attack involving the vETH/BIF market on Ethereum. "
        "The attacker used a very large flash loan to buy BIF, exploited a vulnerable factory path, and then sold back after "
        "the state had been distorted.\n\n"
        "The attacker borrowed essentially the vault's full WETH balance, pushed the BIF-side pricing through the vulnerable path, "
        "and then unwound into WETH before repaying the flash loan."
    ),
    "lauratoken": (
        "An estimated loss of 12.34 ETH (~$41.2K USD) was caused by a flawed liquidity-removal path in the LAURA token "
        "system. The PoC comments explain that `removeLiquidityWhenKIncreases()` could be abused after the attacker "
        "reshaped the WETH/LAURA pair with flash-loaned capital.\n\n"
        "In this incident, the attacker borrowed 30,000 WETH, bought LAURA, added liquidity, triggered the vulnerable "
        "liquidity-removal function, and then removed the manipulated LP position to drain WETH from the pair."
    ),
    "ast": (
        "An estimated loss of about $65K was caused by faulty transfer and liquidity logic in the AST token on BSC. "
        "The attacker could abuse the proxy and pair interaction so that liquidity removal was effectively accounted for twice.\n\n"
        "The attacker flash-borrowed BUSD, swapped into AST, added tokens into the AST/BUSD pair, used `skim()` and `sync()` "
        "to exploit the accounting bug, and then sold the recovered AST back into BUSD."
    ),
    "hydt": (
        "An estimated loss of about $5.8K USDT was caused by unsafe oracle usage in the HYDT minting flow on BSC. "
        "The InitialMintV2 contract used the WBNB/USDT pair price directly to determine mint ratios, allowing the attacker "
        "to manipulate the oracle with a flash loan.\n\n"
        "The attacker flash-borrowed roughly 11 million USDT, pushed the WBNB/USDT spot price to an abnormal level, "
        "called `initialMint()` with 11 BNB to mint excess HYDT, and then unwound through multiple DEX routes to realize profit."
    ),
    "bgm": (
        "An estimated loss of about $450K was caused by a price-manipulation attack against BGM on BSC. "
        "The token's inviter reward mechanism could be abused when multiple accounts shared the same invitee, artificially "
        "inflating inviter rewards and enabling withdrawals from the pair.\n\n"
        "The attacker used a prepared contract, manipulated the reward accounting with large batch transactions, withdrew "
        "value from the BGM pair, and profited after the spot price had been distorted."
    ),
    "harrypotterobamasonic10inu": (
        "An estimated loss of about $243K was caused by ineffective access control in the operator contract used by "
        "HarryPotterObamaSonic10Inu 2.0 on Ethereum. The exploiter abused the `0x433e()` path in the operator contract "
        "to add and remove liquidity in large size, causing dramatic price fluctuations in the token's liquidity pool.\n\n"
        "The attacker repeatedly added and removed liquidity around the BITCOIN/WETH market, extracted value from the "
        "manipulated pool, and later routed part of the proceeds into Tornado Cash."
    ),
    "fortunewheel": (
        "An estimated loss of about $21K was caused by missing access control in FortuneWheel's `swapProfitFees()` "
        "function on BSC. The function was publicly callable even though it swapped contract-owned assets and should have been restricted.\n\n"
        "The attacker first manipulated the LINK/WBNB pricing environment, then called `swapProfitFees()` so that the "
        "FortuneWheel contract sold LINK at the manipulated rate, allowing the attacker to unwind and keep the profit."
    ),
    "paribus": (
        "An estimated loss of about $86K was associated with a price-manipulation attack against Paribus on Arbitrum, "
        "with the initial attack path focusing on roughly $60K in ETH, USDT, and ARB. The exploit combined price manipulation "
        "with a bug in the lending flow.\n\n"
        "The attacker deployed an exploit contract, attempted to manipulate the lending platform's valuation path, and borrow "
        "or siphon assets from the affected Paribus markets before countermeasures were deployed."
    ),
}


@dataclass
class Incident:
    date: str
    name: str
    sources: list[str] = field(default_factory=list)
    chain: str = ""
    attack_tx: str = ""
    attack_contract: str = ""
    victim_contract: str = ""
    note: str = ""
    summary: str = ""
    attack_type_raw: str = ""
    poc_url: str = ""

    def key(self) -> str:
        return normalize_name(self.name)


def normalize_name(name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "", name.lower())
    return ALIASES.get(key, key)


def read_csv(name: str) -> list[dict[str, str]]:
    path = INTERMEDIATE / name
    with path.open() as handle:
        return list(csv.DictReader(handle))


def extract_poc_url(notes: str) -> str:
    match = re.search(r"POC: (https?://\S+)", notes)
    return match.group(1) if match else ""


def raw_url_from_blob(blob_url: str) -> str:
    return blob_url.replace("https://github.com/", "https://raw.githubusercontent.com/").replace("/blob/", "/")


def fetch_poc_metadata(poc_url: str) -> dict[str, str | list[str]]:
    raw_url = raw_url_from_blob(poc_url)
    text = requests.get(raw_url, timeout=30).text

    def grab(pattern: str) -> list[str]:
        return re.findall(pattern, text, flags=re.IGNORECASE)

    attack_txs = grab(r"Attack Tx\s*: ?(https?://[^\s)]+)")
    if not attack_txs:
        attack_txs = grab(r"\btx\s*:\s*(https?://[^\s)]+)")
    if not attack_txs:
        block = re.search(
            r"Attack Tx\s*:\s*((?:\n\s*//?\s*0x[a-fA-F0-9]{64})+)",
            text,
            flags=re.IGNORECASE,
        )
        if block:
            attack_txs = re.findall(r"0x[a-fA-F0-9]{64}", block.group(1))

    attacker_contracts = []
    for label in [
        r"Attack Contract(?:\s*\d+)?\s*: ?(https?://[^\s)]+|0x[a-fA-F0-9]{40})",
        r"Created Attack Contract\s*: ?(https?://[^\s)]+|0x[a-fA-F0-9]{40})",
    ]:
        attacker_contracts.extend(grab(label))

    victim_contracts = grab(r"Vulnerable Contract\s*: ?(https?://[^\s)]+|0x[a-fA-F0-9]{40})")
    attackers = grab(r"Attacker\s*: ?(https?://[^\s)]+|0x[a-fA-F0-9]{40})")
    total_lost = grab(r"Total Lost\s*: ?([^\n]+)")
    reasons = grab(r"reason\s*: ?([^\n]+)")

    chain = infer_chain_from_text(raw_url + "\n" + text)
    return {
        "chain": chain,
        "attack_tx": convert_tx_to_preferred_link(attack_txs[0], chain) if attack_txs else "",
        "attack_contract": ensure_address_link(attacker_contracts[0], chain) if attacker_contracts else "",
        "victim_contract": ensure_address_link(victim_contracts[0], chain) if victim_contracts else "",
        "attacker": ensure_address_link(attackers[0], chain) if attackers else "",
        "loss": total_lost[0] if total_lost else "",
        "reason": reasons[0] if reasons else "",
        "raw_url": raw_url,
    }


def infer_chain_from_text(text: str) -> str:
    lowered = text.lower()
    for domain, chain in CHAIN_MAP.items():
        if domain in lowered:
            return chain
    if "createSelectFork(\"bsc\"" in text or "createSelectFork(\"bsc\"" in lowered:
        return "BSC"
    if "createSelectFork(\"mainnet\"" in text or "mainnet" in lowered:
        return "Ethereum"
    if "arbitrum" in lowered:
        return "Arbitrum"
    if "base" in lowered:
        return "Base"
    if "optimism" in lowered:
        return "Optimism"
    return ""


def ensure_address_link(value: str, chain: str) -> str:
    if value.startswith("http"):
        value = re.sub(r"/token/(0x[a-fA-F0-9]{40})", r"/address/\1", value)
        if "/tx/" in value:
            return ""
        return value
    if not re.fullmatch(r"0x[a-fA-F0-9]{40}", value):
        return value
    base = {
        "Ethereum": "https://etherscan.io/address/",
        "BSC": "https://bscscan.com/address/",
        "Arbitrum": "https://arbiscan.io/address/",
        "Base": "https://basescan.org/address/",
        "Optimism": "https://optimistic.etherscan.io/address/",
    }.get(chain, "")
    return f"{base}{value}" if base else value


def convert_tx_to_preferred_link(value: str, chain: str) -> str:
    if re.fullmatch(r"0x[a-fA-F0-9]{64}", value):
        slug = EXTERNAL_EXPLORER_CHAIN_MAP.get(chain)
        if slug:
            return f"https://app.external_explorer.com/explorer/tx/{slug}/{value}"
        return value

    if "app.external_explorer.com/explorer/tx/" in value or "app.external_explorer.com/external_explorer/explorer/tx/" in value:
        return value

    tx_match = re.search(r"/tx/(0x[a-fA-F0-9]{64})", value)
    if tx_match:
        slug = EXTERNAL_EXPLORER_CHAIN_MAP.get(chain)
        if slug:
            return f"https://app.external_explorer.com/explorer/tx/{slug}/{tx_match.group(1)}"
    return value


def sentence_case_summary(summary: str) -> str:
    return summary.strip()


def clean_loss(loss: str) -> str:
    value = re.sub(r"\s+", " ", loss.strip())
    value = value.replace("US$", "USD").replace("~$", "~ $")
    return value


def summary_to_sentence(incident: Incident) -> str:
    summary = incident.summary.strip()
    if not summary:
        return ""
    if " | " in summary:
        return ""
    return summary


def make_note(incident: Incident, poc_meta: dict[str, str | list[str]] | None = None) -> str:
    override = NOTE_OVERRIDES.get(normalize_name(incident.name))
    if override:
        return override

    summary = summary_to_sentence(incident)
    loss = clean_loss(incident.summary.split("|")[-1]) if " | " in incident.summary else ""
    root = ""
    if poc_meta:
        poc_loss = clean_loss(str(poc_meta.get("loss") or "").strip())
        if poc_loss:
            loss = poc_loss
        root = str(poc_meta.get("reason") or "").strip()

    first = ""
    if summary:
        first = sentence_case_summary(summary)
    elif loss:
        first = f"an estimated loss of {loss}."
    else:
        first = f"a price manipulation incident involving {incident.name}."

    if first and not first.endswith("."):
        first += "."

    second = ""
    if root:
        second = f"The root cause was {root}."
    elif incident.attack_type_raw:
        second = f"The incident was labeled as {incident.attack_type_raw} in the referenced source."

    if incident.poc_url:
        third = "A PoC is available in DeFiHackLabs and was included in the referenced resources."
    else:
        third = ""

    return "\n\n".join(part for part in [first, second, third] if part)


def build_incidents() -> list[Incident]:
    incidents: dict[str, Incident] = {}

    for row in read_csv("web3sec_strict_pm.csv"):
        key = normalize_name(row["project_name"])
        incident = incidents.setdefault(
            key,
            Incident(
                date=row["incident_date"],
                name=row["project_name"],
                summary=row["summary"],
                attack_type_raw=row["attack_type_raw"],
                poc_url=extract_poc_url(row["notes"]),
            ),
        )
        source_url = row["source_url"] or WEB3SEC_PM_VIEW
        if source_url == WEB3SEC_BASE:
            source_url = WEB3SEC_PM_VIEW
        incident.sources.extend(filter(None, [source_url, incident.poc_url]))
        if row["incident_date"] < incident.date:
            incident.date = row["incident_date"]

    for row in read_csv("slowmist_strict_pm.csv"):
        key = normalize_name(row["project_name"])
        incident = incidents.setdefault(
            key,
            Incident(
                date=row["incident_date"],
                name=row["project_name"],
                summary=row["summary"],
                attack_type_raw=row["attack_type_raw"],
            ),
        )
        incident.sources.append(row["source_url"])
        if row["incident_date"] < incident.date:
            incident.date = row["incident_date"]
        if not incident.chain and row["chain"]:
            incident.chain = row["chain"]
        if not summary_to_sentence(incident) and row["summary"]:
            incident.summary = row["summary"]
        if not incident.attack_tx and row["source_url"] and "/tx/" in row["source_url"]:
            incident.attack_tx = row["source_url"]

    # Normalize rows where source publication dates diverge from the on-chain attack date.
    # CompoundFork has multiple source dates: Web3Sec shows 2024-10-26, SlowMist maps to 2024-10-25,
    # while the linked Base tx is timestamped 2024-10-24 UTC. Use the on-chain attack date.
    if "compoundfork" in incidents:
        incidents["compoundfork"].date = "2024-10-24"
    # HYDT is listed earlier by source indexing, but the linked BSC tx resolves to 2024-10-10 UTC.
    if "hydt" in incidents:
        incidents["hydt"].date = "2024-10-10"
    # Paribus source indexing shows 2025-01-17, while the linked Arbitrum tx resolves to 2025-01-18 UTC.
    if "paribus" in incidents:
        incidents["paribus"].date = "2025-01-18"

    # Use ExternalExplorer as supporting resource when project names match or known aliases map.
    for row in read_csv("external_explorer_2024-09_to_2025-02_all.csv"):
        key = normalize_name(row["project_name"])
        if key in incidents:
            incidents[key].sources.append(row["source_url"])

    enriched: list[Incident] = []
    for incident in incidents.values():
        manual = MANUAL_ENRICHMENTS.get(normalize_name(incident.name), {})
        if manual.get("poc_url") and not incident.poc_url:
            incident.poc_url = str(manual["poc_url"])
            incident.sources.append(incident.poc_url)
        poc_meta = fetch_poc_metadata(incident.poc_url) if incident.poc_url else None
        if poc_meta:
            if not incident.chain:
                incident.chain = str(poc_meta["chain"])
            if not incident.attack_tx:
                incident.attack_tx = str(poc_meta["attack_tx"])
            if not incident.attack_contract:
                incident.attack_contract = str(poc_meta["attack_contract"])
            if not incident.victim_contract:
                incident.victim_contract = str(poc_meta["victim_contract"])
        if manual.get("chain") and not incident.chain:
            incident.chain = str(manual["chain"])
        if manual.get("attack_tx") and not incident.attack_tx:
            incident.attack_tx = str(manual["attack_tx"])
        if manual.get("attack_contract") and not incident.attack_contract:
            incident.attack_contract = str(manual["attack_contract"])
        if manual.get("victim_contract") and not incident.victim_contract:
            incident.victim_contract = str(manual["victim_contract"])
        incident.sources.extend(manual.get("extra_sources", []))
        incident.note = make_note(incident, poc_meta)
        # Prefer external_explorer-style tx link where possible.
        if incident.attack_tx and incident.chain:
            incident.attack_tx = convert_tx_to_preferred_link(incident.attack_tx, incident.chain)
        enriched.append(incident)

    # Manually map some source-known aliases/resources to stronger names.
    alias_resource_map = {
        "compoundfork": [
            "https://basescan.org/tx/0x6ab5b7b51f780e8c6c5ddaf65e9badb868811a95c1fd64e86435283074d3149e"
        ],
        "veth": [
            "https://x.com/SlowMist_Team/status/1856987988632457708",
            "https://x.com/ExternalExplorer_xyz/status/1857002671124730233",
        ],
    }
    for incident in enriched:
        incident.sources.extend(alias_resource_map.get(normalize_name(incident.name), []))
        incident.sources = list(dict.fromkeys(filter(None, incident.sources)))

    enriched.sort(key=lambda item: (item.date, item.name.lower()))
    return enriched


def write_final_csv(incidents: Iterable[Incident]) -> None:
    FINAL_OUTPUT.mkdir(parents=True, exist_ok=True)
    path = FINAL_OUTPUT / "shared_sheet_delivery_final.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FINAL_HEADERS)
        writer.writeheader()
        for incident in incidents:
            writer.writerow(
                {
                    "time (format: yyyy-mm-dd)": incident.date,
                    "data resouce (all resources you referenced)": "\n".join(incident.sources),
                    "blockchain platform": incident.chain,
                    "attack transaction (via explorer link, we suggest https://app.external_explorer.com/external_explorer/explorer/)": incident.attack_tx,
                    "attack contract address (via explorer link)": incident.attack_contract,
                    "victim contract address (via explorer link)": incident.victim_contract,
                    "note (you can give note for special cases, or just copy report content)": incident.note,
                }
            )


def write_review_csv(incidents: Iterable[Incident]) -> None:
    FINAL_OUTPUT.mkdir(parents=True, exist_ok=True)
    path = FINAL_OUTPUT / "shared_sheet_delivery_review.csv"
    fieldnames = FINAL_HEADERS + ["project_name", "attack_type_raw", "poc_url"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for incident in incidents:
            writer.writerow(
                {
                    "time (format: yyyy-mm-dd)": incident.date,
                    "data resouce (all resources you referenced)": "\n".join(incident.sources),
                    "blockchain platform": incident.chain,
                    "attack transaction (via explorer link, we suggest https://app.external_explorer.com/external_explorer/explorer/)": incident.attack_tx,
                    "attack contract address (via explorer link)": incident.attack_contract,
                    "victim contract address (via explorer link)": incident.victim_contract,
                    "note (you can give note for special cases, or just copy report content)": incident.note,
                    "project_name": incident.name,
                    "attack_type_raw": incident.attack_type_raw,
                    "poc_url": incident.poc_url,
                }
            )


def main() -> int:
    incidents = build_incidents()
    write_final_csv(incidents)
    write_review_csv(incidents)
    print(f"final incidents: {len(incidents)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
