-- Preferences
local default_tcp_port = 8193
local enable_heur_tcp  = true
local enable_heur_data = true

-- Protocol
local focas = Proto("focas", "FOCAS Custom Protocol")

-- Header fields
local f_sync   = ProtoField.bytes  ("focas.sync",   "Sync Prefix")
local f_origin = ProtoField.uint16 ("focas.origin", "Packet Origin", base.HEX, {
  [0x0001] = "Client → Server (Request)",
  [0x0002] = "Server → Client (Response)",
  [0x0004] = "Server → Client (Response)"
})
local f_type   = ProtoField.uint16 ("focas.type",   "Packet Type", base.HEX, {
  [0x0101] = "Open (Request)",
  [0x0102] = "Open (Response)",
  [0x0201] = "Close (Request)",
  [0x0202] = "Close (Response)",
  [0x2101] = "Generic Cmd (Request)",
  [0x2102] = "Generic Cmd (Response)"
})
local f_len    = ProtoField.uint16 ("focas.len",    "Packet Length (bytes after this field)", base.DEC)
local f_spcnt  = ProtoField.uint16 ("focas.subpacket_count", "Subpacket Count", base.DEC)

-- Subpacket fields
local f_sp_len   = ProtoField.uint16("focas.sp.len",   "Subpacket Length", base.DEC)
local f_sp_dev   = ProtoField.uint16("focas.sp.device","Control Device", base.HEX, {
  [0x0001] = "CNC",
  [0x0002] = "PMC"
})
local f_sp_func  = ProtoField.uint32("focas.sp.func",  "Function", base.HEX)
local f_sp_funcname = ProtoField.string("focas.sp.funcname", "Function Name")

-- Payload helpers
local f_sp_payload = ProtoField.bytes("focas.sp.payload", "Payload")
local f_sp_i32_1 = ProtoField.int32("focas.sp.int32_1", "Int32 #1")
local f_sp_i32_2 = ProtoField.int32("focas.sp.int32_2", "Int32 #2")
local f_sp_i32_3 = ProtoField.int32("focas.sp.int32_3", "Int32 #3")
local f_sp_i32_4 = ProtoField.int32("focas.sp.int32_4", "Int32 #4")
local f_sp_i32_5 = ProtoField.int32("focas.sp.int32_5", "Int32 #5")
local f_sp_dbl_1 = ProtoField.double("focas.sp.double_1", "Double #1")
local f_sp_dbl_2 = ProtoField.double("focas.sp.double_2", "Double #2")
local f_sp_dbl_3 = ProtoField.double("focas.sp.double_3", "Double #3")
local f_sp_u32_1 = ProtoField.uint32("focas.sp.uint32_1", "UInt32 #1")
local f_sp_u32_2 = ProtoField.uint32("focas.sp.uint32_2", "UInt32 #2")
local f_sp_bytes_1 = ProtoField.bytes("focas.sp.bytes_1", "Bytes #1")

focas.fields = {
  f_sync, f_origin, f_type, f_len, f_spcnt,
  f_sp_len, f_sp_dev, f_sp_func, f_sp_funcname,
  f_sp_payload, f_sp_i32_1, f_sp_i32_2, f_sp_i32_3, f_sp_i32_4, f_sp_i32_5,
  f_sp_dbl_1, f_sp_dbl_2, f_sp_dbl_3, f_sp_u32_1, f_sp_u32_2, f_sp_bytes_1
}

-- Registries
local FUNC_NAMES = {
  [0x00010015] = "Read Macro",
  [0x00010018] = "Read Sys Info",
  [0x00010019] = "Read Stat Info",
  [0x000100A8] = "Set Macro (double)"
}
local FUNC_SPECS = { [0x000100A8] = { {"double","Value 1"}, {"double","Value 2"}, {"bytes","Tail",-1} } }
local TYPEFUNC_NAMES = {}
local TYPEFUNC_SPECS = {
  [0x0101] = {
    -- Open Connection Request

  },
  [0x2101] = {
    -- Generic Requests
    [0x000100A8] = {
      -- Write Macro (Double)
      {"int32", "Macro Variable Number"},
      {"bytes", "Fill", 12},
      {"int32", "Macro Value Length (Bytes)"},
      {"double", "Macro Value (double)"}
    }
  },
  [0x2102] = {
    -- Generic Responses
    [0x000100A8] = {
      -- Write Macro (Double)
      {"int32", "Fill"},
      {"int32", "Origin (?)"},
      {"int32", "OK (?)"}
    }
  }
}

-- Helpers
local function has_sync_prefix(tvb, offset)
  if tvb:len() - offset < 4 then return false end
  return tvb(offset,4):bytes():tohex(false) == "A0A0A0A0"
end

local function resolve_name(packet_type, func_id)
  local tmap = TYPEFUNC_NAMES[packet_type]
  if tmap and tmap[func_id] then return tmap[func_id] end
  return FUNC_NAMES[func_id]
end

local function get_spec(packet_type, func_id)
  local tmap = TYPEFUNC_SPECS[packet_type]
  if tmap and (tmap[func_id] ~= nil) then return tmap[func_id] end
  return FUNC_SPECS[func_id]
end

local function decode_payload(tvb, base_off, payload_len, ctx, sp_node)
  local spec = get_spec(ctx.packet_type, ctx.func_id)
  local function show_remaining(off, rem)
    if rem > 0 then sp_node:add(f_sp_payload, tvb(off, rem)):set_text(string.format("Payload (remaining %d bytes)", rem)) end
  end
  if type(spec) == "function" then
    local ok, err = pcall(spec, tvb, base_off, payload_len, sp_node, ctx)
    if not ok then
      sp_node:add_expert_info(PI_MALFORMED, PI_ERROR, "Custom decoder error: "..tostring(err))
      sp_node:add(f_sp_payload, tvb(base_off, payload_len))
    end
    return
  end
  if not spec then
    local to_decode = math.min(payload_len, 20)
    if to_decode >= 4  then sp_node:add(f_sp_i32_1, tvb(base_off+0,4)) end
    if to_decode >= 8  then sp_node:add(f_sp_i32_2, tvb(base_off+4,4)) end
    if to_decode >= 12 then sp_node:add(f_sp_i32_3, tvb(base_off+8,4)) end
    if to_decode >= 16 then sp_node:add(f_sp_i32_4, tvb(base_off+12,4)) end
    if to_decode >= 20 then sp_node:add(f_sp_i32_5, tvb(base_off+16,4)) end
    show_remaining(base_off+to_decode, payload_len - to_decode)
    return
  end
  local off = base_off
  local remaining = payload_len
  local idx_d, idx_i, idx_u, idx_b = 1,1,1,1
  for _, ent in ipairs(spec) do
    local t, lab, len = ent[1], ent[2], ent[3]
    if t == "double" then
      if remaining < 8 then break end
      local field = (idx_d==1 and f_sp_dbl_1) or (idx_d==2 and f_sp_dbl_2) or f_sp_dbl_3
      local n = sp_node:add(field, tvb(off,8)); if lab then n:set_text(string.format("%s: %s", lab, tostring(tvb(off,8):float()))) end
      idx_d = idx_d + 1; off = off + 8; remaining = remaining - 8
    elseif t == "int32" then
      if remaining < 4 then break end
      local field = (idx_i==1 and f_sp_i32_1) or (idx_i==2 and f_sp_i32_2) or (idx_i==3 and f_sp_i32_3) or (idx_i==4 and f_sp_i32_4) or f_sp_i32_5
      local n = sp_node:add(field, tvb(off,4)); if lab then n:append_text(" ("..lab..")") end
      idx_i = idx_i + 1; off = off + 4; remaining = remaining - 4
    elseif t == "uint32" then
      if remaining < 4 then break end
      local field = (idx_u==1 and f_sp_u32_1) or f_sp_u32_2
      local n = sp_node:add(field, tvb(off,4)); if lab then n:append_text(" ("..lab..")") end
      idx_u = idx_u + 1; off = off + 4; remaining = remaining - 4
    elseif t == "bytes" then
      local l = (len == -1) and remaining or (len or 0)
      if l <= 0 or remaining < l then break end
      local n = sp_node:add(f_sp_bytes_1, tvb(off, l))
      n:set_text(string.format("%s: %s", lab or ("Bytes #"..idx_b), tvb(off,l):bytes():tohex(true," ")))
      idx_b = idx_b + 1; off = off + l; remaining = remaining - l
    else
      break
    end
  end
  show_remaining(off, remaining)
end

-- Dissector
function focas.dissector(tvb, pinfo, tree)
  local pktlen = tvb:len()
  local offset = 0
  while offset < pktlen do
    local remaining = pktlen - offset
    if remaining < 12 then pinfo.desegment_len = 12 - remaining; return end
    if not has_sync_prefix(tvb, offset) then return end
    local hdr = offset
    local origin = tvb(hdr+4,2):uint()
    local ptype  = tvb(hdr+6,2):uint()
    local plen   = tvb(hdr+8,2):uint()
    local total  = 10 + plen
    if remaining < total then pinfo.desegment_len = total - remaining; return end

    pinfo.cols.protocol = "FOCAS"
    pinfo.cols.info = string.format("Type 0x%04X | Origin 0x%04X | %d bytes", ptype, origin, total)

    local subtree = tree:add(focas, tvb(offset, total), "FOCAS Packet")
    subtree:add(f_sync,   tvb(hdr,4))
    subtree:add(f_origin, tvb(hdr+4,2))
    subtree:add(f_type,   tvb(hdr+6,2))
    subtree:add(f_len,    tvb(hdr+8,2))
    local spcnt = tvb(hdr+10,2):uint()
    subtree:add(f_spcnt,  tvb(hdr+10,2))

    local sp_off = hdr + 12
    local packet_end = hdr + total

    for i=1, spcnt do
      local sp_remaining = packet_end - sp_off
      if sp_remaining < 8 then subtree:add(focas, tvb(sp_off, sp_remaining), string.format("Subpacket %d (truncated header)", i)); break end
      local sp_len = tvb(sp_off,2):uint()
      if sp_len < 8 or sp_remaining < sp_len then pinfo.desegment_len = math.max(0, (sp_off + sp_len) - (hdr + remaining)); return end
      local node = subtree:add(focas, tvb(sp_off, sp_len), string.format("Subpacket %d", i))
      node:add(f_sp_len,  tvb(sp_off,2))
      node:add(f_sp_dev,  tvb(sp_off+2,2))
      local func_id = tvb(sp_off+4,4):uint()
      local fnode = node:add(f_sp_func, tvb(sp_off+4,4))
      local nm = resolve_name(ptype, func_id)
      if nm then fnode:append_text(string.format(" (%s)", nm)); node:add(f_sp_funcname, nm) end
      local pay_off = sp_off + 8
      local pay_len = sp_len - 8
      if pay_len > 0 then
        local ctx = { packet_type = ptype, origin = origin, device = tvb(sp_off+2,2):uint(), func_id = func_id }
        decode_payload(tvb, pay_off, pay_len, ctx, node)
      end
      sp_off = sp_off + sp_len
    end
    offset = hdr + total
  end
end

-- Heuristics/binding
local function heur_dissect(tvb, pinfo, tree)
  if tvb:len() < 12 then return false end
  if not has_sync_prefix(tvb, 0) then return false end
  local declared = tvb(8,2):uint()
  local total = 10 + declared
  if total <= tvb:len() then focas.dissector(tvb, pinfo, tree); return true end
  pinfo.desegment_len = total - tvb:len(); return true
end

if enable_heur_tcp then focas:register_heuristic("tcp", heur_dissect) end
if enable_heur_data then pcall(function() focas:register_heuristic("data", heur_dissect) end) end
if default_tcp_port and default_tcp_port > 0 then
  local tcp_table = DissectorTable.get("tcp.port")
  tcp_table:add(default_tcp_port, focas)
end
