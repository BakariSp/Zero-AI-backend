import socket
import subprocess
import os
import platform

# Two Supabase hosts to test
direct_host = "db.ecwdxlkvqiqyjffcovby.supabase.co"
pooler_host = "aws-0-ap-southeast-1.pooler.supabase.com"

def test_host(hostname, port):
    print(f"\n===== Testing {hostname} on port {port} =====")
    
    # Try Python's socket resolution
    try:
        ip_address = socket.gethostbyname(hostname)
        print(f"✅ Socket resolution successful: {hostname} -> {ip_address}")
    except Exception as e:
        print(f"❌ Socket resolution failed: {e}")
        return False

    # Try to ping the host (may be blocked by firewall)
    print("\nTrying to ping the host (might be blocked):")
    param = "-n" if platform.system().lower() == "windows" else "-c"
    try:
        result = subprocess.call(["ping", param, "1", hostname], 
                              stdout=subprocess.DEVNULL, 
                              stderr=subprocess.DEVNULL)
        if result == 0:
            print(f"✅ Ping successful to {hostname}")
        else:
            print(f"⚠️ Ping failed with code {result} (may be blocked by firewall)")
    except Exception as e:
        print(f"⚠️ Ping failed: {e}")

    # Try to check outbound connectivity to the port
    print(f"\nTrying to check connectivity to port {port}:")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        
        # Try to resolve first
        try:
            ip_addr = socket.gethostbyname(hostname)
            result = sock.connect_ex((ip_addr, port))
            if result == 0:
                print(f"✅ Port {port} is open on {hostname}")
                return True
            else:
                print(f"❌ Port {port} is closed on {hostname} (result={result})")
        except Exception as e:
            print(f"❌ Could not resolve hostname for connection test: {e}")
        
        sock.close()
    except Exception as e:
        print(f"❌ Socket test failed: {e}")
    
    return False

def test_connection_string(conn_string, name):
    """Test if a connection string can at least resolve the hostname"""
    print(f"\n===== Testing {name} Connection String =====")
    # Parse the connection string to get hostname and port
    # Example: postgresql://username:password@hostname:port/dbname
    
    # Extract hostname and port from the connection string
    try:
        parts = conn_string.split('@')[1].split('/')[0]
        hostname = parts.split(':')[0]
        port = int(parts.split(':')[1]) if ':' in parts else 5432
        
        print(f"Extracted hostname: {hostname}")
        print(f"Extracted port: {port}")
        
        return test_host(hostname, port)
    except Exception as e:
        print(f"❌ Error parsing connection string: {e}")
        return False

# Test both connection types
print("=================================================")
print("TESTING SUPABASE CONNECTION OPTIONS")
print("=================================================")

direct_conn = "postgresql://postgres:password@db.ecwdxlkvqiqyjffcovby.supabase.co:5432/postgres"
pooler_conn = "postgresql://postgres:password@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"

# Test direct connection
direct_result = test_connection_string(direct_conn, "Direct")

# Test pooler connection
pooler_result = test_connection_string(pooler_conn, "Transaction Pooler")

print("\n=================================================")
print("CONNECTION TEST RESULTS")
print("=================================================")
print(f"Direct Connection: {'✅ WORKING' if direct_result else '❌ FAILED'}")
print(f"Transaction Pooler: {'✅ WORKING' if pooler_result else '❌ FAILED'}")
print("\nRECOMMENDATION:")

if pooler_result and not direct_result:
    print("→ Use the Transaction Pooler connection (IPv4 compatible)")
elif direct_result and not pooler_result:
    print("→ Use the Direct connection")
elif direct_result and pooler_result:
    print("→ Both connections work! Using Direct is generally better for long-running applications")
else:
    print("→ Neither connection works. Please add your IP to the allowed list in Supabase.")
    print(f"   Your IPv4: {socket.gethostbyname(socket.gethostname())}")
    print("   Add it here: https://supabase.com/dashboard/project/ecwdxlkvqiqyjffcovby/settings/database") 