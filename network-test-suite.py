#!/usr/bin/env python3

import os
import sys
import time
import json
import socket
import statistics
import subprocess
import platform
import csv
import argparse
import random
import string
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

class NetworkPerformanceTester:
    def __init__(self, output_file=None, iterations=3, iperf_server=None, 
                 speedtest=True, local_test=True, duration=10):
        self.iterations = iterations
        self.output_file = output_file
        self.iperf_server = iperf_server
        self.should_run_speedtest = speedtest
        self.run_local_test = local_test
        self.duration = duration
        
        self.system_info = self._get_system_info()
        self.results = []
        
        # Check for required tools
        self.has_iperf3 = self._check_tool("iperf3")
        self.has_speedtest = self._check_tool("speedtest-cli") or self._check_tool("speedtest")
        
        if not self.has_iperf3:
            print("Warning: iperf3 not found. Some tests will be skipped.")
            print("Install with: 'apt install iperf3' (Linux) or 'brew install iperf3' (macOS)")
        
        if not self.has_speedtest and self.run_speedtest:
            print("Warning: speedtest-cli not found. Internet speed tests will be skipped.")
            print("Install with: 'pip install speedtest-cli'")
    
    def _check_tool(self, tool):
        """Check if a command-line tool is available"""
        try:
            subprocess.check_call(
                [tool, "--version"], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def _get_system_info(self):
        """Gather system and network interface information"""
        info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "hostname": socket.gethostname(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "interfaces": self._get_network_interfaces()
        }
        return info
    
    def _get_network_interfaces(self):
        """Get network interface information based on OS"""
        interfaces = {}
        
        if platform.system() == "Linux":
            try:
                # Use ip command for Linux
                output = subprocess.check_output("ip -o addr show", shell=True, text=True)
                for line in output.strip().split('\n'):
                    parts = line.split()
                    if len(parts) >= 4 and parts[2] == "inet":
                        iface = parts[1]
                        ip = parts[3].split('/')[0]
                        interfaces[iface] = {
                            "ip": ip,
                            "details": self._get_interface_details_linux(iface)
                        }
            except Exception as e:
                print(f"Error getting network interfaces: {e}")
        
        elif platform.system() == "Darwin":  # macOS
            try:
                # Use ifconfig for macOS
                output = subprocess.check_output("ifconfig", shell=True, text=True)
                current_iface = None
                for line in output.strip().split('\n'):
                    if not line.startswith('\t'):
                        parts = line.split(":")
                        if len(parts) > 0:
                            current_iface = parts[0]
                    elif current_iface and "inet " in line:
                        ip = line.strip().split()[1]
                        interfaces[current_iface] = {
                            "ip": ip,
                            "details": self._get_interface_details_macos(current_iface)
                        }
            except Exception as e:
                print(f"Error getting network interfaces: {e}")
        
        return interfaces
    
    def _get_interface_details_linux(self, iface):
        """Get detailed info about a network interface on Linux"""
        details = {}
        
        # Get link speed and status
        try:
            output = subprocess.check_output(f"ethtool {iface} 2>/dev/null || echo 'Speed: Unknown'", 
                                            shell=True, text=True)
            for line in output.strip().split('\n'):
                line = line.strip()
                if "Speed:" in line:
                    details["speed"] = line.split("Speed:")[1].strip()
                elif "Link detected:" in line:
                    details["link"] = line.split("Link detected:")[1].strip()
                elif "Duplex:" in line:
                    details["duplex"] = line.split("Duplex:")[1].strip()
        except Exception:
            details["speed"] = "Unknown"
            details["link"] = "Unknown"
            
        # Check if wireless
        try:
            output = subprocess.check_output(f"iwconfig {iface} 2>/dev/null || echo ''", 
                                           shell=True, text=True)
            if "ESSID:" in output:
                details["type"] = "wireless"
                # Extract ESSID
                if "ESSID:" in output:
                    essid_part = output.split("ESSID:")[1].split("\n")[0]
                    details["essid"] = essid_part.strip().strip('"')
                # Extract frequency
                if "Frequency:" in output:
                    freq_part = output.split("Frequency:")[1].split(" ")[0]
                    details["frequency"] = freq_part.strip()
                # Extract bit rate
                if "Bit Rate=" in output:
                    rate_part = output.split("Bit Rate=")[1].split(" ")[0]
                    details["bit_rate"] = rate_part.strip()
                # Extract signal level
                if "Signal level=" in output:
                    signal_part = output.split("Signal level=")[1].split(" ")[0]
                    details["signal"] = signal_part.strip()
            else:
                details["type"] = "wired"
        except Exception:
            details["type"] = "unknown"
        
        return details
    
    def _get_interface_details_macos(self, iface):
        """Get detailed info about a network interface on macOS"""
        details = {}
        
        # Check if wireless
        try:
            # Only check wireless details if the interface starts with 'en'
            if iface.startswith('en'):
                output = subprocess.check_output(
                    f"/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I 2>/dev/null || echo ''", 
                    shell=True, text=True
                )
                
                if "SSID:" in output:
                    details["type"] = "wireless"
                    # Extract SSID
                    for line in output.strip().split('\n'):
                        line = line.strip()
                        if "SSID:" in line:
                            details["essid"] = line.split("SSID:")[1].strip()
                        elif "channel:" in line:
                            details["channel"] = line.split("channel:")[1].strip()
                        elif "agrCtlRSSI:" in line:
                            details["signal"] = line.split("agrCtlRSSI:")[1].strip() + " dBm"
                        elif "lastTxRate:" in line:
                            details["bit_rate"] = line.split("lastTxRate:")[1].strip() + " Mbps"
                else:
                    details["type"] = "wired"
                    
                # For both wired and wireless, try to get link speed
                try:
                    linkspeed_output = subprocess.check_output(
                        f"networksetup -getmedia {iface} 2>/dev/null || echo 'Device not found'", 
                        shell=True, text=True
                    )
                    if "active =" in linkspeed_output:
                        for line in linkspeed_output.strip().split('\n'):
                            if "media active:" in line.lower() and "baseT" in line:
                                details["speed"] = line.split(":")[1].strip()
                except Exception:
                    details["speed"] = "Unknown"
            else:
                details["type"] = "other"
                details["speed"] = "Unknown"
        except Exception as e:
            details["type"] = "unknown"
            details["speed"] = "Unknown"
            
        return details
    
    def run_latency_jitter_test(self, host="8.8.8.8", count=100):
        """Run a ping test to measure latency and jitter"""
        print(f"Running latency and jitter test to {host} ({count} pings)...")
        
        ping_param = "-c" if platform.system() != "Windows" else "-n"
        
        try:
            cmd = f"ping {ping_param} {count} {host}"
            output = subprocess.check_output(cmd, shell=True, text=True, timeout=count+30)
            
            # Parse the ping output
            lines = output.strip().split('\n')
            times = []
            packet_loss = "100%"
            
            for line in lines:
                if "time=" in line:
                    try:
                        # Extract ping time (works for both Linux and macOS)
                        time_str = line.split("time=")[1].split()[0].strip()
                        # Remove 'ms' if present and convert to float
                        times.append(float(time_str.replace("ms", "")))
                    except (IndexError, ValueError):
                        pass
                elif "packet loss" in line:
                    try:
                        for part in line.split(","):
                            if "packet loss" in part:
                                packet_loss = part.strip().split()[0]
                                break
                    except Exception:
                        pass
            
            if times:
                # Calculate jitter (average deviation between consecutive pings)
                jitter = 0
                if len(times) > 1:
                    diffs = [abs(times[i] - times[i-1]) for i in range(1, len(times))]
                    jitter = sum(diffs) / len(diffs)
                
                return {
                    "min": min(times),
                    "max": max(times),
                    "avg": statistics.mean(times),
                    "mdev": statistics.stdev(times) if len(times) > 1 else 0,
                    "jitter": jitter,
                    "packet_loss": packet_loss,
                    "samples": len(times)
                }
            else:
                return {
                    "min": None,
                    "max": None,
                    "avg": None,
                    "mdev": None,
                    "jitter": None,
                    "packet_loss": packet_loss,
                    "samples": 0
                }
        except Exception as e:
            print(f"Error during ping test to {host}: {e}")
            return {
                "min": None,
                "max": None,
                "avg": None,
                "mdev": None,
                "jitter": None,
                "packet_loss": "100%",
                "samples": 0,
                "error": str(e)
            }
    
    def run_iperf3_test(self, server, port=5201, duration=10, protocol="tcp", reverse=False):
        """Run an iperf3 test to measure throughput"""
        if not self.has_iperf3:
            return {"error": "iperf3 not installed"}
        
        print(f"Running iperf3 {protocol.upper()} {'download' if reverse else 'upload'} test to {server}:{port} for {duration}s...")
        
        cmd = f"iperf3 -c {server} -p {port} -t {duration} -J"
        if protocol.lower() == "udp":
            cmd += " -u"
        if reverse:
            cmd += " -R"
        
        try:
            output = subprocess.check_output(cmd, shell=True, text=True, timeout=duration+15)
            try:
                result = json.loads(output)
                if protocol.lower() == "tcp":
                    sent = result.get("end", {}).get("sum_sent", {})
                    received = result.get("end", {}).get("sum_received", {})
                    
                    # Get the appropriate result based on direction
                    data = received if reverse else sent
                    
                    return {
                        "protocol": "TCP",
                        "bits_per_second": data.get("bits_per_second"),
                        "retransmits": result.get("end", {}).get("sum", {}).get("retransmits", 0),
                        "sender": not reverse,
                        "mbps": data.get("bits_per_second", 0) / 1000000
                    }
                else:  # UDP
                    summary = result.get("end", {}).get("sum", {})
                    return {
                        "protocol": "UDP",
                        "bits_per_second": summary.get("bits_per_second"),
                        "jitter_ms": summary.get("jitter_ms"),
                        "lost_packets": summary.get("lost_packets"),
                        "packets": summary.get("packets"),
                        "lost_percent": summary.get("lost_percent", 0),
                        "sender": not reverse,
                        "mbps": summary.get("bits_per_second", 0) / 1000000
                    }
            except json.JSONDecodeError:
                print("Error parsing iperf3 JSON output")
                # If JSON parse fails, try to extract basic information
                mbps = None
                for line in output.split('\n'):
                    if "sender" in line and "Mbits/sec" in line:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if "Mbits/sec" in part and i > 0:
                                try:
                                    mbps = float(parts[i-1])
                                    break
                                except (ValueError, IndexError):
                                    pass
                
                return {
                    "protocol": protocol.upper(),
                    "mbps": mbps,
                    "output": output,
                    "parse_error": "Could not parse JSON output"
                }
        except subprocess.CalledProcessError as e:
            print(f"iperf3 error: {e}")
            return {"error": f"iperf3 failed with return code {e.returncode}", "output": e.output if hasattr(e, 'output') else None}
        except subprocess.TimeoutExpired:
            print("iperf3 test timed out")
            return {"error": "Timeout expired"}
        except Exception as e:
            print(f"Error during iperf3 test: {e}")
            return {"error": str(e)}
    
    def run_speedtest(self):
        """Run internet speed test using speedtest-cli"""
        if not self.has_speedtest:
            return {"error": "speedtest-cli not installed"}
        
        print("Running internet speed test (this may take a minute)...")
        
        try:
            # First try with speedtest-cli
            try:
                output = subprocess.check_output("speedtest-cli --json", shell=True, text=True, timeout=120)
            except (subprocess.SubprocessError, FileNotFoundError):
                # Fall back to 'speedtest' command if available
                output = subprocess.check_output("speedtest --format=json", shell=True, text=True, timeout=120)
            
            try:
                result = json.loads(output)
                
                # Handle different JSON formats between speedtest and speedtest-cli
                if "download" in result and isinstance(result["download"], dict):
                    # New speedtest format
                    return {
                        "download_mbps": result["download"]["bandwidth"] * 8 / 1000000,
                        "upload_mbps": result["upload"]["bandwidth"] * 8 / 1000000,
                        "ping_ms": result["ping"]["latency"],
                        "jitter_ms": result["ping"].get("jitter", None),
                        "server": result.get("server", {}).get("name", "Unknown"),
                        "server_country": result.get("server", {}).get("country", "Unknown")
                    }
                else:
                    # Old speedtest-cli format
                    return {
                        "download_mbps": result["download"] / 1000000,  # Convert to Mbps
                        "upload_mbps": result["upload"] / 1000000,      # Convert to Mbps
                        "ping_ms": result["ping"],
                        "server": result.get("server", {}).get("sponsor", "Unknown"),
                        "server_country": result.get("server", {}).get("country", "Unknown")
                    }
            except json.JSONDecodeError:
                # If JSON parse fails, try to extract basic information
                download = upload = ping = None
                for line in output.split('\n'):
                    if "Download:" in line:
                        try:
                            download = float(line.split(':')[1].strip().split(' ')[0])
                        except (ValueError, IndexError):
                            pass
                    elif "Upload:" in line:
                        try:
                            upload = float(line.split(':')[1].strip().split(' ')[0])
                        except (ValueError, IndexError):
                            pass
                    elif "Ping:" in line:
                        try:
                            ping = float(line.split(':')[1].strip().split(' ')[0])
                        except (ValueError, IndexError):
                            pass
                
                return {
                    "download_mbps": download,
                    "upload_mbps": upload,
                    "ping_ms": ping,
                    "parse_error": "Could not parse JSON output"
                }
                
        except subprocess.CalledProcessError as e:
            print(f"speedtest error: {e}")
            return {"error": f"Speed test failed with return code {e.returncode}"}
        except subprocess.TimeoutExpired:
            print("speedtest timed out")
            return {"error": "Timeout expired"}
        except Exception as e:
            print(f"Error during speed test: {e}")
            return {"error": str(e)}
    
    def get_local_network_ip(self):
        """Get an IP address on the local network"""
        local_ips = []
        for iface, data in self.system_info["interfaces"].items():
            ip = data.get("ip")
            if ip and not ip.startswith("127.") and not ip.startswith("::1"):
                local_ips.append(ip)
        
        if local_ips:
            return local_ips[0]
        return None
    
    def run_local_transfer_test(self, size_mb=100):
        """Run a test to measure file transfer speed on the local network"""
        if not self.run_local_test:
            return {"error": "Local test disabled"}
        
        local_ip = self.get_local_network_ip()
        if not local_ip:
            return {"error": "Could not find local network IP"}
        
        print(f"Running local network file transfer test (creating {size_mb}MB test file)...")
        
        # Create a temporary file with random data
        temp_filename = f"net_test_{int(time.time())}_{random.randint(1000, 9999)}.bin"
        try:
            if platform.system() == "Linux":
                subprocess.check_call(
                    f"dd if=/dev/urandom of={temp_filename} bs=1M count={size_mb}", 
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            else:  # macOS
                with open(temp_filename, 'wb') as f:
                    f.write(os.urandom(size_mb * 1024 * 1024))
            
            # Start a simple HTTP server in a separate process
            server_cmd = f"python3 -m http.server 8765"
            server_process = subprocess.Popen(
                server_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            
            try:
                # Give the server time to start
                time.sleep(2)
                
                # Download the file using curl and measure the time
                start_time = time.time()
                download_result = subprocess.check_output(
                    f"curl -s -o /dev/null -w '%{speed_download}' http://{local_ip}:8765/{temp_filename}",
                    shell=True, text=True, timeout=300
                )
                end_time = time.time()
                
                elapsed_time = end_time - start_time
                transfer_speed_mbps = (size_mb * 8) / elapsed_time
                
                try:
                    # Try to parse curl's speed output if available
                    curl_speed = float(download_result.strip())
                    transfer_speed_mbps_curl = curl_speed * 8 / 1000000  # Convert bytes/s to Mbps
                except (ValueError, TypeError):
                    transfer_speed_mbps_curl = None
                
                return {
                    "file_size_mb": size_mb,
                    "elapsed_seconds": elapsed_time,
                    "transfer_speed_mbps": transfer_speed_mbps,
                    "transfer_speed_mbps_curl": transfer_speed_mbps_curl
                }
                
            finally:
                # Make sure to terminate the server
                server_process.terminate()
                try:
                    server_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server_process.kill()
        
        except Exception as e:
            print(f"Error during local transfer test: {e}")
            return {"error": str(e)}
        
        finally:
            # Clean up the temporary file
            try:
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
            except Exception:
                pass
    
    def run_tests(self):
        """Run all network performance tests"""
        print(f"\n{'=' * 60}")
        print(f"Network Performance Test Suite - {self.system_info['timestamp']}")
        print(f"System: {self.system_info['os']} {self.system_info['os_version']}")
        print(f"Hostname: {self.system_info['hostname']}")
        print("Network Interfaces:")
        for iface, data in self.system_info['interfaces'].items():
            ip = data.get("ip")
            details = data.get("details", {})
            iface_type = details.get("type", "unknown")
            speed = details.get("speed", "Unknown")
            
            if iface_type == "wireless":
                essid = details.get("essid", "Unknown")
                signal = details.get("signal", "Unknown")
                print(f"  - {iface}: {ip} (Wireless, SSID: {essid}, Signal: {signal}, Speed: {speed})")
            else:
                print(f"  - {iface}: {ip} (Wired, Speed: {speed})")
        
        print(f"{'=' * 60}\n")
        
        for i in range(self.iterations):
            print(f"\nIteration {i+1} of {self.iterations}")
            print(f"{'-' * 40}")
            
            iteration_results = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "iteration": i + 1
            }
            
            # Latency and jitter test (Google DNS)
            latency_result = self.run_latency_jitter_test(host="8.8.8.8", count=100)
            iteration_results["latency_test"] = latency_result
            
            if latency_result["avg"] is not None:
                print(f"Latency test results (8.8.8.8):")
                print(f"  Min/Avg/Max/StdDev = {latency_result['min']:.2f}/{latency_result['avg']:.2f}/{latency_result['max']:.2f}/{latency_result['mdev']:.2f} ms")
                print(f"  Jitter = {latency_result['jitter']:.2f} ms")
                print(f"  Packet Loss = {latency_result['packet_loss']}")
            else:
                print(f"Latency test failed: {latency_result.get('error', 'Unknown error')}")
            
            # iperf3 tests (if server specified)
            if self.iperf_server:
                # TCP upload test
                tcp_upload = self.run_iperf3_test(self.iperf_server, protocol="tcp", duration=self.duration)
                iteration_results["iperf_tcp_upload"] = tcp_upload
                
                if "error" not in tcp_upload:
                    print(f"iperf3 TCP upload test results:")
                    print(f"  Throughput: {tcp_upload['mbps']:.2f} Mbps")
                    if "retransmits" in tcp_upload:
                        print(f"  Retransmits: {tcp_upload['retransmits']}")
                else:
                    print(f"iperf3 TCP upload test failed: {tcp_upload.get('error', 'Unknown error')}")
                
                # TCP download test
                tcp_download = self.run_iperf3_test(self.iperf_server, protocol="tcp", duration=self.duration, reverse=True)
                iteration_results["iperf_tcp_download"] = tcp_download
                
                if "error" not in tcp_download:
                    print(f"iperf3 TCP download test results:")
                    print(f"  Throughput: {tcp_download['mbps']:.2f} Mbps")
                    if "retransmits" in tcp_download:
                        print(f"  Retransmits: {tcp_download['retransmits']}")
                else:
                    print(f"iperf3 TCP download test failed: {tcp_download.get('error', 'Unknown error')}")
                
                # UDP test
                udp_test = self.run_iperf3_test(self.iperf_server, protocol="udp", duration=self.duration)
                iteration_results["iperf_udp_test"] = udp_test
                
                if "error" not in udp_test:
                    print(f"iperf3 UDP test results:")
                    print(f"  Throughput: {udp_test['mbps']:.2f} Mbps")
                    if "jitter_ms" in udp_test:
                        print(f"  Jitter: {udp_test['jitter_ms']:.2f} ms")
                    if "lost_percent" in udp_test:
                        print(f"  Packet Loss: {udp_test['lost_percent']:.2f}%")
                else:
                    print(f"iperf3 UDP test failed: {udp_test.get('error', 'Unknown error')}")
            
            # Internet speed test
            if self.should_run_speedtest:
                speed_test = self.run_speedtest()
                iteration_results["speedtest"] = speed_test
                
                if "error" not in speed_test:
                    print(f"Internet speed test results:")
                    print(f"  Download: {speed_test['download_mbps']:.2f} Mbps")
                    print(f"  Upload: {speed_test['upload_mbps']:.2f} Mbps")
                    print(f"  Ping: {speed_test['ping_ms']:.2f} ms")
                    if "jitter_ms" in speed_test and speed_test["jitter_ms"] is not None:
                        print(f"  Jitter: {speed_test['jitter_ms']:.2f} ms")
                    if "server" in speed_test:
                        print(f"  Server: {speed_test['server']} ({speed_test.get('server_country', 'Unknown')})")
                else:
                    print(f"Internet speed test failed: {speed_test.get('error', 'Unknown error')}")
            
            # Local network transfer test (optional)
            if self.run_local_test:
                local_test = self.run_local_transfer_test(size_mb=100)
                iteration_results["local_transfer"] = local_test
                
                if "error" not in local_test:
                    print(f"Local network transfer test results:")
                    print(f"  File size: {local_test['file_size_mb']} MB")
                    print(f"  Transfer time: {local_test['elapsed_seconds']:.2f} seconds")
                    print(f"  Transfer speed: {local_test['transfer_speed_mbps']:.2f} Mbps")
                else:
                    print(f"Local network transfer test failed: {local_test.get('error', 'Unknown error')}")
            
            self.results.append(iteration_results)
            
            # Sleep between iterations (except the last one)
            if i < self.iterations - 1:
                print(f"\nWaiting 5 seconds before next test iteration...")
                time.sleep(5)
        
        self._save_results()
        self._print_summary()
    
    def _save_results(self):
        """Save test results to file if specified"""
        if not self.output_file:
            return
        
        try:
            # Create the necessary directories if they don't exist
            os.makedirs(os.path.dirname(os.path.abspath(self.output_file)), exist_ok=True)
            
            # Save raw data as JSON for detailed analysis
            json_file = self.output_file.replace('.csv', '.json')
            with open(json_file, 'w') as f:
                json.dump({
                    "system_info": self.system_info,
                    "results": self.results,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }, f, indent=2)
            
            print(f"\nRaw results saved to {json_file}")
            
            # Create a simplified CSV file with the most important metrics
            with open(self.output_file, 'w', newline='') as csvfile:
                # Create header row based on available tests
                fieldnames = ["timestamp", "iteration"]
                
                # Add latency fields
                fieldnames.extend([
                    "latency_min_ms", "latency_avg_ms", "latency_max_ms", 
                    "jitter_ms", "packet_loss"
                ])
                
                # Add iperf3 fields if applicable
                if self.iperf_server:
                    fieldnames.extend([
                        "tcp_upload_mbps", "tcp_download_mbps", 
                        "tcp_upload_retransmits", "tcp_download_retransmits",
                        "udp_mbps", "udp_jitter_ms", "udp_loss_percent"
                    ])
                
                # Add speedtest fields if applicable
                if self.should_run_speedtest:
                    fieldnames.extend([
                        "internet_download_mbps", "internet_upload_mbps", "internet_ping_ms", 
                        "internet_jitter_ms"
                    ])
                
                # Add local transfer test fields if applicable
                if self.run_local_test:
                    fieldnames.extend([
                        "local_transfer_mbps", "local_transfer_time_s"
                    ])
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                # Write data rows
                for result in self.results:
                    row = {
                        "timestamp": result["timestamp"],
                        "iteration": result["iteration"]
                    }
                    
                    # Add latency data
                    latency = result.get("latency_test", {})
                    row["latency_min_ms"] = latency.get("min")
                    row["latency_avg_ms"] = latency.get("avg")
                    row["latency_max_ms"] = latency.get("max")
                    row["jitter_ms"] = latency.get("jitter")
                    row["packet_loss"] = latency.get("packet_loss")
                    
                    # Add iperf3 data if applicable
                    if self.iperf_server:
                        tcp_upload = result.get("iperf_tcp_upload", {})
                        tcp_download = result.get("iperf_tcp_download", {})
                        udp_test = result.get("iperf_udp_test", {})
                        
                        row["tcp_upload_mbps"] = tcp_upload.get("mbps")
                        row["tcp_upload_retransmits"] = tcp_upload.get("retransmits")
                        row["tcp_download_mbps"] = tcp_download.get("mbps")
                        row["tcp_download_retransmits"] = tcp_download.get("retransmits")
                        row["udp_mbps"] = udp_test.get("mbps")
                        row["udp_jitter_ms"] = udp_test.get("jitter_ms")
                        row["udp_loss_percent"] = udp_test.get("lost_percent")
                    
                    # Add speedtest data if applicable
                    if self.should_run_speedtest:
                        speed_test = result.get("speedtest", {})
                        row["internet_download_mbps"] = speed_test.get("download_mbps")
                        row["internet_upload_mbps"] = speed_test.get("upload_mbps")
                        row["internet_ping_ms"] = speed_test.get("ping_ms")
                        row["internet_jitter_ms"] = speed_test.get("jitter_ms")
                    
                    # Add local transfer test data if applicable
                    if self.run_local_test:
                        local_test = result.get("local_transfer", {})
                        row["local_transfer_mbps"] = local_test.get("transfer_speed_mbps")
                        row["local_transfer_time_s"] = local_test.get("elapsed_seconds")
                    
                    writer.writerow(row)
            
            print(f"CSV summary saved to {self.output_file}")
        except Exception as e:
            print(f"Error saving results to file: {e}")
    
    def _print_summary(self):
        """Print a summary of the test results"""
        print(f"\n{'=' * 60}")
        print("SUMMARY")
        print(f"{'=' * 60}")
        
        # Latency and jitter statistics
        latency_avgs = []
        jitter_avgs = []
        
        for result in self.results:
            latency = result.get("latency_test", {})
            if latency.get("avg") is not None:
                latency_avgs.append(latency["avg"])
            if latency.get("jitter") is not None:
                jitter_avgs.append(latency["jitter"])
        
        if latency_avgs:
            print("\nLatency Statistics:")
            print(f"  Average latency: {statistics.mean(latency_avgs):.2f} ms")
            print(f"  Min latency: {min(latency_avgs):.2f} ms")
            print(f"  Max latency: {max(latency_avgs):.2f} ms")
            if len(latency_avgs) > 1:
                print(f"  Latency StdDev: {statistics.stdev(latency_avgs):.2f} ms")
        
        if jitter_avgs:
            print("\nJitter Statistics:")
            print(f"  Average jitter: {statistics.mean(jitter_avgs):.2f} ms")
            print(f"  Min jitter: {min(jitter_avgs):.2f} ms")
            print(f"  Max jitter: {max(jitter_avgs):.2f} ms")
            if len(jitter_avgs) > 1:
                print(f"  Jitter StdDev: {statistics.stdev(jitter_avgs):.2f} ms")
        
        # iperf3 statistics
        if self.iperf_server:
            # TCP upload
            tcp_upload_speeds = []
            for result in self.results:
                tcp_upload = result.get("iperf_tcp_upload", {})
                if "mbps" in tcp_upload:
                    tcp_upload_speeds.append(tcp_upload["mbps"])
            
            if tcp_upload_speeds:
                print("\niPerf3 TCP Upload Statistics:")
                print(f"  Average: {statistics.mean(tcp_upload_speeds):.2f} Mbps")
                print(f"  Min: {min(tcp_upload_speeds):.2f} Mbps")
                print(f"  Max: {max(tcp_upload_speeds):.2f} Mbps")
                if len(tcp_upload_speeds) > 1:
                    print(f"  StdDev: {statistics.stdev(tcp_upload_speeds):.2f} Mbps")
            
            # TCP download
            tcp_download_speeds = []
            for result in self.results:
                tcp_download = result.get("iperf_tcp_download", {})
                if "mbps" in tcp_download:
                    tcp_download_speeds.append(tcp_download["mbps"])
            
            if tcp_download_speeds:
                print("\niPerf3 TCP Download Statistics:")
                print(f"  Average: {statistics.mean(tcp_download_speeds):.2f} Mbps")
                print(f"  Min: {min(tcp_download_speeds):.2f} Mbps")
                print(f"  Max: {max(tcp_download_speeds):.2f} Mbps")
                if len(tcp_download_speeds) > 1:
                    print(f"  StdDev: {statistics.stdev(tcp_download_speeds):.2f} Mbps")
            
            # UDP
            udp_speeds = []
            udp_jitters = []
            udp_losses = []
            
            for result in self.results:
                udp_test = result.get("iperf_udp_test", {})
                if "mbps" in udp_test:
                    udp_speeds.append(udp_test["mbps"])
                if "jitter_ms" in udp_test:
                    udp_jitters.append(udp_test["jitter_ms"])
                if "lost_percent" in udp_test:
                    udp_losses.append(udp_test["lost_percent"])
            
            if udp_speeds:
                print("\niPerf3 UDP Statistics:")
                print(f"  Average throughput: {statistics.mean(udp_speeds):.2f} Mbps")
                if udp_jitters:
                    print(f"  Average jitter: {statistics.mean(udp_jitters):.2f} ms")
                if udp_losses:
                    print(f"  Average packet loss: {statistics.mean(udp_losses):.2f}%")
        
        # Internet speed test statistics
        if self.should_run_speedtest:
            download_speeds = []
            upload_speeds = []
            pings = []
            
            for result in self.results:
                speed_test = result.get("speedtest", {})
                if "download_mbps" in speed_test:
                    download_speeds.append(speed_test["download_mbps"])
                if "upload_mbps" in speed_test:
                    upload_speeds.append(speed_test["upload_mbps"])
                if "ping_ms" in speed_test:
                    pings.append(speed_test["ping_ms"])
            
            if download_speeds:
                print("\nInternet Speed Test Statistics:")
                print(f"  Average download: {statistics.mean(download_speeds):.2f} Mbps")
                print(f"  Average upload: {statistics.mean(upload_speeds):.2f} Mbps")
                print(f"  Average ping: {statistics.mean(pings):.2f} ms")
        
        # Local transfer test statistics
        if self.run_local_test:
            transfer_speeds = []
            
            for result in self.results:
                local_test = result.get("local_transfer", {})
                if "transfer_speed_mbps" in local_test:
                    transfer_speeds.append(local_test["transfer_speed_mbps"])
            
            if transfer_speeds:
                print("\nLocal Network Transfer Statistics:")
                print(f"  Average speed: {statistics.mean(transfer_speeds):.2f} Mbps")
                print(f"  Min speed: {min(transfer_speeds):.2f} Mbps")
                print(f"  Max speed: {max(transfer_speeds):.2f} Mbps")
                if len(transfer_speeds) > 1:
                    print(f"  StdDev: {statistics.stdev(transfer_speeds):.2f} Mbps")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Network Performance Test Suite")
    parser.add_argument("-o", "--output", type=str, help="Output CSV file", default="network_perf_results.csv")
    parser.add_argument("-i", "--iterations", type=int, default=3, help="Number of test iterations")
    parser.add_argument("-s", "--server", type=str, help="iPerf3 server address")
    parser.add_argument("-t", "--time", type=int, default=10, help="Duration of bandwidth tests in seconds")
    parser.add_argument("--no-speedtest", action="store_true", help="Skip internet speed test")
    parser.add_argument("--no-local", action="store_true", help="Skip local network transfer test")
    
    args = parser.parse_args()
    
    tester = NetworkPerformanceTester(
        output_file=args.output,
        iterations=args.iterations,
        iperf_server=args.server,
        speedtest=not args.no_speedtest,
        local_test=not args.no_local,
        duration=args.time
    )
    tester.run_tests()
    