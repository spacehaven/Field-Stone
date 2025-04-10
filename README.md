# Field-Stone
AI Generated Python Based Network Testing Suite

Generated with Claude Sonnet 3.7 desktop, modified a little with Roo and Sonnet 3.5. 

I'm nearing the completion of a complete home network upgrade, and decided I want to test the network performance before and after. It's 7 in the morning, I haven't finished my first coffee, and I'm not caffinated enough to search for and learn an existing test suite. So this happened.

## Prompts 

> I'm about to upgrade my home network's router, switches, cabling, and access points. I'd like to perform some very simple before-and-after tests. Is there a simple python test suite that can run under both my wireless mac laptop and wired linux desktop?

> Those tests look good, but I was primarily interested in speed/throughput, jitter, latency, those kind of performance stats.

## Response

Below is Claude's most recent response:

---

This new script is specifically designed to measure network performance metrics like throughput, latency, and jitter – exactly what you need for your upgrade assessment. It's cross-platform (works on both your Linux desktop and macOS laptop) and provides comprehensive testing.

#### Key Features:

1. Comprehensive Performance Metrics:

Latency and jitter testing (using ping)
Throughput testing (using iperf3)
Internet speed testing (download/upload speeds using speedtest-cli)
Local network file transfer testing


2. Network Interface Detection:

Automatically detects and reports on wired/wireless interfaces
Shows connection details (speed, SSID for wireless, signal strength)


3. Detailed Reporting:

Saves results in both CSV and JSON formats
Provides statistical summaries of all tests
Captures before/after comparison data



#### How to Use:

1. Install Dependencies:
```bash
# For Linux:
sudo apt install iperf3
pip3 install speedtest-cli

# For macOS:
brew install iperf3
pip3 install speedtest-cli
```

2. Before Upgrade Testing:
```bash
# Basic test with internet speed test
python3 network_perf_test.py -o before_upgrade.csv

# If you have an iperf3 server on your network (recommended for best results):
python3 network_perf_test.py -o before_upgrade.csv -s 192.168.1.100

# Run more iterations for better statistical significance
python3 network_perf_test.py -o before_upgrade.csv -s 192.168.1.100 -i 5
```

3. After Upgrade Testing:
```bash
# Run the same command you used before the upgrade
python3 network_perf_test.py -o after_upgrade.csv -s 192.168.1.100 -i 5
```

4. Comparison:
After running the tests, you'll have CSV files that you can compare in Excel/Google Sheets, or you can use the JSON files for more detailed analysis.

#### iperf3 Server Note:
For best results, set up an iperf3 server on your network. This can be:

Another computer running: `iperf3 -s`

A router with iperf3 capability (many custom firmware routers support this)

A Raspberry Pi or other always-on device

This will give you the most accurate throughput measurements within your LAN.

