-- Define the protocol name and description
local proto_dante = Proto("DanTeProtocol", "DanTe Protocol")

-- Define the header fields
local f_message_type = ProtoField.uint16("dante.message_type", "Message Type", base.HEX)
local f_src_port = ProtoField.uint32("dante.src_port", "Source Port", base.HEX)
local f_dst_port = ProtoField.uint32("dante.dst_port", "Destination Port", base.HEX)
local f_total_length = ProtoField.uint32("dante.total_length", "Total Length", base.DEC)
local f_offset_fragment = ProtoField.uint32("dante.offset_fragment", "Fragment Offset", base.DEC)
local f_fragment_size = ProtoField.uint32("dante.fragment_size", "Fragment Size", base.DEC)
local f_crc32_fragment = ProtoField.uint32("dante.crc32_fragment", "CRC32", base.HEX)
local f_data = ProtoField.bytes("dante.data", "Data")

-- Assign fields to the protocol
proto_dante.fields = {f_message_type, f_src_port, f_dst_port, f_total_length, f_offset_fragment, f_fragment_size, f_crc32_fragment, f_data}

-- Define the UDP ports to analyze
local udp_ports = {10, 20}

-- Packet dissecting function
function proto_dante.dissector(buffer, pinfo, tree)
    -- Verify if the packet length is less than the minimum header size (26 bytes)
    if buffer:len() < 26 then
        return
    end

    -- Set the protocol name in the Wireshark Protocol column
    pinfo.cols.protocol = proto_dante.name

    -- Create a subtree for DanTe Protocol data
    local subtree = tree:add(proto_dante, buffer(), "DanTe Protocol Data")

    -- Extract and display the header fields
    subtree:add(f_message_type, buffer(0, 2))        -- Message Type: 2 bytes
    subtree:add(f_src_port, buffer(2, 4))           -- Source Port: 4 bytes
    subtree:add(f_dst_port, buffer(6, 4))           -- Destination Port: 4 bytes
    subtree:add(f_total_length, buffer(10, 4))      -- Total Length: 4 bytes
    subtree:add(f_offset_fragment, buffer(14, 4))   -- Offset Fragment: 4 bytes
    subtree:add(f_fragment_size, buffer(18, 4))     -- Fragment Size: 4 bytes
    subtree:add(f_crc32_fragment, buffer(22, 4))    -- CRC32: 4 bytes

    -- Determine the start of the data field
    local data_start = 26  -- Data starts after the first 26 bytes
    if buffer:len() > data_start then
        local data_len = buffer:len() - data_start
        subtree:add(f_data, buffer(data_start, data_len))
    end

    -- Get the message type
    local message_type = buffer(0, 2):uint()

    -- Determine the label based on the message type
    local label = ""
    if message_type == 0x00 then
        label = "Initialization"
    elseif message_type == 0x01 then
        label = "Data Transfer"
    elseif message_type == 0x02 then
        label = "Acknowledgment"
    elseif message_type == 0x03 then
        label = "Error Message"
    else
        label = "Unknown Message Type"
    end

    -- Update the Info column in Wireshark
    pinfo.cols.info:set(label)
    subtree:append_text(" [" .. label .. "]")
end

-- Register the protocol for the specified UDP ports
local udp_table = DissectorTable.get("udp.port")
for _, port in ipairs(udp_ports) do
    udp_table:add(port, proto_dante)
end
