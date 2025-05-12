import socket
import sys
import threading
import os
import tkinter as tk
from tkinter import filedialog
import zlib
import struct
import random
import time

"""
    Lucas Daniel Espitia Corredor
    PKS_B
    Semester Project
    2024 in Winter Semester
    FIIT 
    STU        
    Copyright
    Implementation: 
    Protocol:
    
general:  | flag | srcPort | dstPort | total length | offset | frag max size (x) | crc32 | data   |
bytes:    |   2  |    4    |    4    |      4       |    4   |        4          |    4  | n <  x |
   
    
    
    
"""


class P2PNode:
    def __init__(self, local_port, peer_ip, peer_port):
        self.local_port = local_port
        self.peer_ip = peer_ip
        self.peer_port = peer_port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('', self.local_port))  # Bind to any available IP
        self.running = True
        self.sending = True
        self.receiving = True
        self.fragment_size = 1024 # Fragment size in bytes

        #First connection
        self.first_time = False
        self.handshake_event = threading.Event()
        #Keep-alive utils
        self.keep_alive_attempts = 3
        self.keep_alive_time = 5
        self.user_input = ""

        #Classes
        self.protocol = ProtocolUDP()
        self.sender = Sender(self)
        self.receiver = Receiver(self)

        #Threads
        self.keep_alive_event = threading.Event()
        threading.Thread(target=self.start_receiver, daemon=True).start()
        threading.Thread(target=self.start_keep_alive, daemon=True).start()

        threading.Thread(target=self.start_sending).start()

#Start main loops
    def start_receiver(self):
        """
            Thread: Receives messages and resets the keep-alive timer when a message is received.
            """
        while self.running:
            if self.receiving:
                try:
                    fragment, addr = self.socket.recvfrom(1550)
                    self.receiver.receive_and_route(fragment)
                    self.keep_alive_event.set()  # Reset the keep-alive timer
                except OSError as e:
                    #ignore errors
                    if 'timed out' in str(e) or 'resource temporarily unavailable' in str(e):
                        pass
                    else:
                        continue
                except Exception as e:
                    print(f"Error: {e}")
                    continue

    def start_sending(self):
        """
            Thread: Sends messages after handshake, processes user input.
            """
        self.handshake_event.wait()
        while self.running:
            if self.sending:
                try:
                    user_input = input(f"Enter message or command: {self.user_input}")
                    self.user_input = user_input
                    if not self.running:
                        break
                    self.handle_input(user_input)
                except Exception as e:
                    print(f"Error: {e}")
                    break
            else:
                continue

    def start_keep_alive(self):
        """
            Thread: Send the keep alive when the timer is 0
            """
        while self.running and self.keep_alive_attempts > 0:
            if self.keep_alive_event.is_set():
                self.keep_alive_event.clear() #Restart the time
                self.keep_alive_attempts = 3
            else:
                self.sender.send_keep_alive()
                if self.first_time:
                    self.keep_alive_attempts -= 1

            time.sleep(self.keep_alive_time)
        if self.keep_alive_attempts <= 0:
            print("Connection lost. No response from peer.")
            self.stop()

# Handle functions

    def set_handshake_complete(self):
        self.handshake_event.set()
        Utils.print_line()
        print("Handshake complete! You can now send messages.")
        print("Default directory to save files has been assigned")
        print("Directory: Current Directory")
        print("Type '/help' for more information about the commands")
        Utils.print_line()

    def handle_keep_ack(self):
        self.keep_alive_event.is_set()
        if not self.first_time:
           self.first_time_m()

    def handle_error(self):
        """Prompt user to choose between sending corrupted text or file."""
        while True:  # Keep asking until the user provides a valid input
            print("Select the type of error to send:")
            print("1 - Corrupt a text message")
            print("2 - Corrupt a file")
            print("3 - Cancel")

            user_choice = input("Enter your choice (1/2/3): ")

            if user_choice == "1":
                # Corrupt a text message
                message = input("Enter the text message to send: ")
                self.sender.send_message(message, 1024, is_error=True)
                break

            elif user_choice == "2":
                # Corrupt a file
                self.sender.send_file(self.fragment_size, is_error=True)
                break

            elif user_choice == "3":
                print("Error sending canceled.")
                break

            else:
                print("Invalid choice. Please enter 1, 2, or 3.")

#Stop function

    def stop(self):
        """Stops the node connection."""
        self.running = False
        self.handshake_event.set()
        try:
            self.socket.close()  # Close the socket gracefully
        except OSError:
            print("Socket already closed.")

        print("Connection closed.")
        exit()

#INPUT and COMMANDS and More
    def first_time_m(self):

         self.set_handshake_complete()
         self.first_time = True

    def handle_input(self, user_input):
        """Handle user input based on whether it's text or a command."""
        if not user_input:
            print("No message to send")
            return
        if user_input.startswith("/"):
            self.handle_command(user_input)
            self.user_input = ""
        else:
            self.false_sending()
            self.sender.send_message(user_input, 1024)
            self.user_input = ""

    def handle_command(self, command):
        commands = {
            "/help": Utils.show_help,
            "/file":  lambda: self.sender.send_file(self.fragment_size),
            "/path": self.save_path,
            "/frag": self.set_fragment_size,
            "/error": self.handle_error,
            "/exit": self.stop,
        }
        handler = commands.get(command)
        if handler:
            handler()
        else:
            print(f"Unrecognized command: {command}")
            self.true_sending()

    def save_path(self):

        # User can choose where he wants to download the file
        self.false_sending()
        root = tk.Tk()
        root.withdraw()
        save_path = filedialog.askdirectory(title="Select Folder to Save the File")
        #Save path that user save
        if save_path:
            print(f"Path saved: {save_path}")
            self.receiver.set_save_path(save_path)
        else:
            print("No path selected, try again")
        self.true_sending()

    def set_fragment_size(self):
        """Changes the maximum fragment size."""
        try:
            size = int(input("Enter new fragment size (in bytes): "))
            if Utils.is_valid_size_fragment(size):
                self.fragment_size = size
                print(f"Fragment size set to {self.fragment_size} bytes.")
            else:
                print("Error: Fragment size must be between 12 bytes and 1500 bytes.")
        except ValueError:
            print("Error: Please enter a valid numeric value for fragment size.")

    def true_sending(self):
        self.sending = True

    def false_sending(self):
        self.sending = False

#Class receiver
class Receiver:
    def __init__(self, node):

        self.node = node
        self.protocol = node.protocol
        self.sender = node.sender

        self.type_message = None
        self.received_fragments = []
        self.missing_fragments = []
        self.count_fragments = 0
        self.total_fragments = None

        self.save_path = os.getcwd()


    def receive_and_route(self, fragment):
        """Centralized receive function that routes messages based on their type."""
        #Parse the header and extract
        if not self.node.first_time:
            self.node.first_time_m()

        header_data = fragment[:self.protocol.header_size]
        data = fragment[self.protocol.header_size:]
        header_fragment = self.protocol.parse_header(header_data)

        message_type = header_fragment[0]
        if message_type in [0,1]:
            self.node.false_sending()
            self.handle_fragment(header_fragment, data)
        elif message_type in [2,3]:
            self.handle_keep_alive(message_type)
        elif message_type in [4, 5]:
            self.handle_sending_confirmation(message_type)
        elif message_type in [6]:
            self.handle_missing_fragments(data) #NACK
        else:
            print("Unknown message type")

    def check_received_fragments(self):
        """Check if all fragments have been received correctly."""
        for index, fragment in enumerate(self.received_fragments):
            if fragment is None and index not in self.missing_fragments:
                self.missing_fragments.append(index)

        if not self.missing_fragments:
            if self.type_message == 0:
                self.handle_received_message()
            elif self.type_message == 1:
                self.handle_received_file()
            self.reset_variables()
            self.sender.ack_confirmation()
        else:
            self.request_missing_fragments()
            self.missing_fragments = []

    def request_missing_fragments(self):
        """Request retransmission of missing fragments."""
        if not self.missing_fragments:
            return
        print(f"Requesting retransmission for fragments: {self.missing_fragments}")

        max_indices_per_packet = 256
        # Take only the first block of up to 256 missing indexes
        block = self.missing_fragments[:max_indices_per_packet]

        missing_index_bytes = b''.join(
            fragment.to_bytes(4, byteorder='big') for fragment in block
        )
        self.sender.request_fragments(missing_index_bytes)
        self.missing_fragments = []

    def handle_sending_confirmation(self, message_type):
        """Handle ACK confirmation last fragment and stop sending"""
        if message_type == 4:
            self.check_received_fragments()
        else:
            self.sender.stop_sending()

    def handle_missing_fragments(self, header_data):
        self.sender.resend_fragments(header_data)

    def handle_fragment(self, header_fragment, data):
        """
           Handle a received fragment with Selective Repeat protocol.
           """
        # 1. Get the Data of the header
        message_type = header_fragment[0]
        total_length = header_fragment[3]
        offset_fragment = header_fragment[4]
        fragment_size = header_fragment[5]
        received_crc32 = header_fragment[6]
        # 2. Verify CRC32 of the received fragment
        calculated_crc32 = Utils.calculate_crc(data)

        crc_valid = received_crc32 == calculated_crc32  # True or false
        # when there is no fragmentation
        if offset_fragment == 0:
            self.type_message = message_type
            print("\n")
            Utils.print_line()
            print("Received message without fragmentation")
            if crc_valid:
                print(f"Total size: {len(data)} bytes")
                self.received_fragments = [data]
                self.total_fragments = 1
            else:
                print("Message corrupted, requesting retransmission..")
                self.missing_fragments = [offset_fragment]
        else:
            # 3. Initialize racking on the first fragment
            if self.total_fragments is None:
                print("\n")
                Utils.print_line()
                print("Received message with fragmentation")
                print(f"Total size: {total_length}")
                self.total_fragments = (total_length // fragment_size) + 1

                # Initialize received_fragments
                self.received_fragments = [None] * self.total_fragments
                self.type_message = message_type
            # 4. Handle the received fragment
            if crc_valid:
                # Only store if the fragment is new
                if self.received_fragments[offset_fragment - 1] is None:
                    self.received_fragments[offset_fragment - 1] = data  # Store data, sort it and mark as saved
                    print(f"Fragment {offset_fragment} / {self.total_fragments} received with size {len(data)}.")
            else:
                # If fragment is corrupt, mark it as None (no data) in the list
                if self.received_fragments[offset_fragment - 1] is None:
                    self.missing_fragments.append(offset_fragment - 1)  # Corrupted fragment
                print(f"Fragment {offset_fragment} / {self.total_fragments} marked for retransmission.")

    def handle_keep_alive(self, message_type):
        """
        Handle Keep-Alive messages based on their type.
        Type 2: Keep-Alive request, respond with confirmation.
        Type 3: Keep-Alive confirmation, reset attempts.
        """
        if message_type == 2:
            self.sender.respond_to_keep()
        elif message_type == 3:
            self.node.handle_keep_ack()

    def handle_received_message(self):
        complete_message = b''.join(self.received_fragments)
        message = complete_message.decode('utf-8')
        print(f"Received message: {message}")
        Utils.print_line()
        sys.stdout.write(f"Enter message or command: ")
        sys.stdout.flush()

    def handle_received_file(self):
        """This method handles receiving the entire file."""
        # Rebuild the complete file
        complete_file_data = b''.join(self.received_fragments)

        file_name = input("Enter the name of the file to save: ")
        print(f"test221")

        if not file_name:
            file_name = "default_name"

        if not file_name.endswith('.txt'):
            file_name += '.txt'

        file_path = os.path.join(self.save_path, file_name)

        with open(file_path, "wb") as file:
            file.write(complete_file_data)

        file_size = len(complete_file_data)
        print(f"File received successfully!")
        # print(f"Transfer time: {transfer_duration:.2f} seconds")
        print(f"File size: {file_size} bytes")
        print(f"File saved to: {self.save_path}")

    def set_save_path(self, save_path):
        self.save_path = save_path

    def reset_variables(self):
        """Reset variables after processing a message to prepare for the next one."""
        self.count_fragments = 0
        self.total_fragments = None
        self.type_message = None
        self.received_fragments = []
        self.missing_fragments = []
        self.node.true_sending()

#class sender
class Sender:
    def __init__(self, node):
        self.node = node
        self.local_port = node.local_port
        self.peer_ip = node.peer_ip
        self.peer_port = node.peer_port
        self.socket = node.socket
        #For fragmentation
        self.protocol = node.protocol

        self.type_message = None
        self.sent_fragments = []
        self.count_fragments = 0
        self.total_fragments = None

    def resend_fragments(self, data):
        """
        Retransmit specific fragments based on the indices received in the data.
        """
        # Unpack the indices from the received data
        num_indices = len(data) // 4
        missing_indices = [
            int.from_bytes(data[i * 4:(i + 1) * 4], byteorder='big') for i in range(num_indices)
        ]

        print(f"Retransmission requested for fragments: {missing_indices}")

        # Loop through the missing indices and retransmit the corresponding fragments
        for index in missing_indices:
            if 0 <= index < len(self.sent_fragments):
                corrected_fragment = self.fix_and_resend_fragment(index)
                if corrected_fragment:
                    try:
                        print(f"Retransmitting fragment {index + 1}...")
                        self.socket.sendto(corrected_fragment, (self.peer_ip, self.peer_port))
                    except Exception as e:
                        print(f"Error retransmitting fragment {index + 1}: {e}")
                else:
                    print(f"Failed to fix fragment {index + 1}. Skipping retransmission.")
            else:
                print(f"Invalid fragment index: {index}")

        # Send a final acknowledgment after retransmitting all fragments
        self.send_final_ack()

    def fix_and_resend_fragment(self, index):
        """
        Fix the CRC32 of a corrupt fragment and return it.
        """
        if 0 <= index < len(self.sent_fragments):
            # Get the corrupt fragment
            corrupt_fragment = self.sent_fragments[index]

            # Unpack the fragment and save type
            header_corrupted = corrupt_fragment[:self.protocol.header_size]
            data = corrupt_fragment[self.protocol.header_size:]

            header_fragment = self.protocol.parse_header(header_corrupted)
            self.type_message = header_fragment[0]

            # Correct the CRC32
            correct_crc32 = Utils.calculate_crc(data)

            correct_header = self.protocol.create_header(
                header_fragment[0], header_fragment[1], header_fragment[2],
                header_fragment[3], header_fragment[4], header_fragment[5],
                correct_crc32
            )

            #Create the fragment fixed and return it
            fixed_fragment = correct_header + data
            return fixed_fragment
        else:
            print(f"Index {index} out of range.")
            return None

    def send_fragment(self, fragments, message_type, is_retransmit=False):
        # Send the (possibly corrupted) fragments
        for i, fragment in enumerate(fragments):
            try:
                if message_type in [0,1]:
                    if not is_retransmit:
                        fragment_size = len(fragment[self.protocol.header_size:])
                        print(f"Sending fragment {i + 1}/{len(fragments)} with size {fragment_size} bytes...")
                        self.sent_fragments.append(fragment)
                self.socket.sendto(fragment, (self.peer_ip, self.peer_port))
            except OSError:
                print("Failed to send fragment. Connection may be closed.")
        if message_type in [0,1]:

            self.send_final_ack()
            Utils.print_line()

    #WORKING
    def stop_sending(self):
        self.sent_fragments = []
        self.type_message = None
        self.node.true_sending()

    def ack_confirmation(self):
        self.send_data(b'',
                       0,
                       5)

    def send_keep_alive(self):
        """Send a keep-alive message to the peer."""
        self.send_data(b'',
                       0,
                       message_type=2)

    def request_fragments(self, data_bytes):
        """Send the index requested to the sender"""
        try:
            self.send_data(data_bytes, 1024, message_type=6)
        except Exception as e:
            print(f"Failed to send missing fragments request: {e}")

    def send_final_ack(self):
        self.send_data(b'',
                       0,
                       message_type=4)

    def respond_to_keep(self):
        """Respond and send a keep-alive message to the peer."""
        self.send_data(b'',
                      0,
                      message_type=3)

    def send_data(self, data, fragment_size, message_type, is_error=False):
        """ General method to send both text messages and files with optional error simulation """
        if not self.socket:
            print("Socket is closed. Cannot send data.")
            return
        # Create the fragments
        fragments = self.protocol.create_message(message_type,
                                                 self.local_port,
                                                 self.peer_port,
                                                 fragment_size,
                                                 data)
        # When user wants to send error manually
        # Print the total number of fragments and the fragment size
        if message_type in [0,1]:
            print(f"Total fragments to send: {len(fragments)}")
            print(f"Fragment max size: {fragment_size} bytes")
        if is_error:
            # Randomly select fragment (or the only one)
            num_fragments_to_corrupt = min(300, len(fragments))

            # Randomly select 300 (or fewer) unique fragments to corrupt
            corrupted_indices = random.sample(range(len(fragments)), num_fragments_to_corrupt)

            for fragment_index in corrupted_indices:
                # Corrupt the selected fragment
                corrupted_fragment = fragments[fragment_index]
                corrupted_header = self.corrupt_crc(corrupted_fragment)

                # Replace the original fragment with the corrupted one
                fragments[fragment_index] = corrupted_header + corrupted_fragment[self.protocol.header_size:]

                # Print the fragment being corrupted
                print(f"Simulating error on fragment {fragment_index + 1}")

        self.send_fragment(fragments, message_type)

    def send_message(self, user_input, fragment_size, is_error=False):
        """Send a text message, adding CRC for validation."""
        # Convert user input to bytes
        data = user_input.encode('utf-8')

        # Send the message data using the general method
        Utils.print_line()
        self.send_data(data,
                       fragment_size,
                       message_type=0,
                       is_error=is_error)

    def send_file(self, fragment_size, is_error=False):
        """Send a file with CRC validation. If the file size exceeds the fragment size, it will be fragmented."""
        # Select the file to send using Tkinter dialog
        self.node.false_sending()
        root = tk.Tk()
        root.withdraw()  # Hide the Tkinter main window

        file_path = filedialog.askopenfilename(
            title="Select the file to send",
            filetypes=[("Text Files", "*.txt")]
        )

        if not file_path:
            print("No file selected.")
            self.node.true_sending()
            return

        # Get the file name (basename) and file size
        file_name = os.path.basename(file_path)  # Get the file name from the path
        file_size_bytes = os.path.getsize(file_path)  # Get the file size in bytes
        file_size_mb = file_size_bytes / (1024 * 1024)  # Convert bytes to megabytes

        # Print the file name and size in MB
        Utils.print_line()
        print(f"Selected file: {file_name}")
        print(f"File size: {file_size_mb:.2f} MB")

        # Open the file and read as bytes
        with open(file_path, 'rb') as file:
            data = file.read()

        # Send the file data using the general method
        self.send_data(data, fragment_size, message_type=1, is_error=is_error)

    def corrupt_crc(self, corrupted_fragment):
        """Corrupt the CRC32 in the fragment and return the new header."""
        # Parse the header of the corrupted fragment
        header_fragment = self.protocol.parse_header(corrupted_fragment[:self.protocol.header_size])
        # Corrupt the CRC32 (invert all bits)
        corrupted_crc32 = (header_fragment[6]^ 0xFFFFFFFF)

        # Rebuild the header with the corrupted CRC32
        corrupted_header = self.protocol.create_header(
            header_fragment[0], header_fragment[1], header_fragment[2], header_fragment[3], header_fragment[4],
            header_fragment[5], corrupted_crc32
        )
        return corrupted_header

#Class protocol
class ProtocolUDP:
    def __init__(self):
        self.header_format ="!HIIIIII" #Header H (26 bytes reserved in total)
        self.header_size = struct.calcsize(self.header_format)

    def create_header(self, message_type, src_port, dst_port, total_length, offset_fragment, fragment_size, crc32_fragment):
        """ Creates the header for the message """
        return struct.pack(self.header_format, message_type, src_port, dst_port, total_length, offset_fragment,
                           fragment_size, crc32_fragment)

    def parse_header(self, header_data):
        """ Extracts the header data """
        return struct.unpack(self.header_format, header_data)

    def create_message(self, message_type, src_port, dst_port, fragment_size, data):
        """Creates a complete message with header and CRC32, with total length and fragment size."""
        length = len(data)
        fragments = []

        # Calculate total length of the message
        total_length = len(data)

        if length <= fragment_size:
            # No fragmentation needed, just one fragment
            offset_fragment = 0
            crc32_fragment = Utils.calculate_crc(data)
            header_fragment = self.create_header(message_type, src_port, dst_port, total_length, offset_fragment,
                                                 fragment_size, crc32_fragment)
            fragments.append(header_fragment + data)

        else:
            num_fragments = (length // fragment_size) + (1 if length % fragment_size != 0 else 0)
            for i in range(num_fragments):
                #Create the index and get the text in that part
                start_index = i * fragment_size
                end_index = start_index + fragment_size
                fragment_data = data[start_index:end_index]
                #Put one offset each time, it will increase, starting in
                offset_fragment = i + 1
                crc32_fragment = Utils.calculate_crc(fragment_data)

                header_fragment = self.create_header(message_type, src_port, dst_port, total_length, offset_fragment,
                                                     fragment_size, crc32_fragment)
                fragments.append(header_fragment + fragment_data)

        return fragments

#Utils
class Utils:
    @staticmethod
    def is_valid_ip(ip_address):
        """Validate the IP address format and range."""
        parts = ip_address.split(".")
        if len(parts) != 4:
            return False
        for part in parts:
            if not part.isdigit():
                return False
            num = int(part)
            if num < 0 or num > 255:
                return False
        return True

    @staticmethod
    def is_valid_port(port):
        """Validate port range (0 - 65535)."""
        return 0 <= port <= 65535

    @staticmethod
    def is_valid_size_fragment(size):
        """Validate the fragment size (should be between 12 and 1500)."""
        return 12 <= size <= 1500

    @staticmethod
    def calculate_crc(data: bytes) -> int:
        """Calculate CRC-32 for the given data."""
        return zlib.crc32(data)  # For text data (string)

    @staticmethod
    def verify_crc(data, expected_crc):
        """Verify if the CRC of the received data matches the expected CRC."""
        return Utils.calculate_crc(data) == expected_crc

    @staticmethod
    def show_help():
        """Displays the available commands."""
        print("/file - Send file")
        print("/path - Change path to receive files")
        print("/frag - Change fragment size")
        print("/error - Send test with error")
        print("/exit - Exit")
        Utils.print_line()

    @staticmethod
    def print_line():
        """Print a line separator."""
        print(f"**---------------------------------------------------**")

def main():
    # Request and validate the local port
    while True:
        try:
            local_port = int(input("Enter local port: "))
            if Utils.is_valid_port(local_port):
                break
            else:
                print("Port must be between 0 and 65535.")
        except ValueError:
            print("Error: Please enter a valid numeric port.")

    # Request and validate the peer IP
    while True:
        peer_ip = input("Enter peer node IP: ")
        if Utils.is_valid_ip(peer_ip):
            break  # Exit the loop if the IP is valid
        else:
            print("Error: Invalid IP address format. Please enter again. (255.255.255.255).")

    # Request and validate the peer port
    while True:
        try:
            peer_port = int(input("Enter peer node port: "))
            if Utils.is_valid_port(peer_port):
                if local_port != peer_port:  # Ensure the ports are different
                    break  # Exit the loop if the port is valid and different
                else:
                    print("Error: Local port and peer port must be different! Please enter again.")
            else:
                print("Error: Peer port must be in the range 0-65535. Please enter again.")
        except ValueError:
            print("Error: Please enter a valid numeric peer port.")

    # Create and start the P2P node
    print("Waiting for connection...")
    P2PNode(local_port, peer_ip, peer_port)

if __name__ == "__main__":
    main()

