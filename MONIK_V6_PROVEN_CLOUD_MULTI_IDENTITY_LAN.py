#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import ipaddress
import json
import os
import pathlib
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

APP_TITLE = "MoniK V6 STATUS MATCH EXACT TOKEN IDENTITY"
SSH_TARGET = "root@217.160.149.188"
MAX_UPLOAD = 80 * 1024 * 1024
LOCK = threading.RLock()
STATE: dict[str, Any] = {"model": {"devices": [], "source_name": None}, "tuya_account": None, "tuya_account_job": None, "selected_session_imported": False, "selected_session_error": None}


def extract_tuya_sharing_session(raw: Any) -> dict | None:
    """Extract one complete Tuya sharing session without exposing it."""
    dicts = []

    def walk(value):
        if isinstance(value, dict):
            dicts.append(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(raw)

    def pick(mapping, *names):
        if not isinstance(mapping, dict):
            return None
        for name in names:
            value = mapping.get(name)
            if value not in (None, "", [], {}):
                return value
        return None

    def first_global(*names):
        for mapping in dicts:
            value = pick(mapping, *names)
            if value not in (None, "", [], {}):
                return value
        return None

    for row in dicts:
        token_candidates = [
            row.get("token_info"),
            row.get("tokenInfo"),
            row.get("token"),
            row,
        ]
        for token in token_candidates:
            if not isinstance(token, dict):
                continue
            access = pick(token, "access_token", "accessToken")
            refresh = pick(token, "refresh_token", "refreshToken")
            if not access or not refresh:
                continue

            endpoint = pick(row, "endpoint", "api_endpoint", "apiEndpoint") or first_global(
                "endpoint", "api_endpoint", "apiEndpoint"
            )
            terminal = pick(row, "terminal_id", "terminalId", "terminal") or first_global(
                "terminal_id", "terminalId", "terminal"
            )
            user_code = pick(row, "user_code", "userCode") or first_global(
                "user_code", "userCode"
            )
            if not endpoint or not terminal or not user_code:
                continue

            return {
                "user_code": str(user_code),
                "terminal_id": str(terminal),
                "endpoint": str(endpoint),
                "username": pick(row, "username", "user_name", "userName")
                or first_global("username", "user_name", "userName"),
                "token_info": {
                    "t": pick(token, "t") or first_global("t"),
                    "uid": pick(token, "uid") or first_global("uid"),
                    "expire_time": pick(token, "expire_time", "expireTime")
                    or first_global("expire_time", "expireTime"),
                    "access_token": str(access),
                    "refresh_token": str(refresh),
                },
            }
    return None


KNOWN_SUFFIXES = (
    "_overcharge_switch", "_switch_1", "_switch_2", "_switch_3", "_switch_4",
    "_switch_5", "_switch_6", "_switch_7", "_switch_8", "_all",
)
ID_KEYS = ("deviceId", "device_id", "devId", "dev_id", "yandex_id", "external_id", "external_device_id", "id")
HINT_KEYS = {
    "capabilities", "properties", "status", "function", "functions", "status_range",
    "statusRange", "specifications", "category", "product_id", "productId",
    "local_key", "localKey", "mac", "ip", "lan_ip", "local_ip", "online",
    "codeNames", "local_strategy", "dpStatusRelationDTOS", "skill_id", "device_info",
}

REMOTE_JS = r'''
"use strict";
const https=require("https"),crypto=require("crypto"),fs=require("fs"),readline=require("readline");
const CLIENT="HA_3y9q4ak7g4ephrvke",SCHEMA="haauthorize",LOGIN="apigw.iotbing.com",YBASE="https://api.iot.yandex.net/v1.0",TUYA_SESSION_FILE="/opt/monik-tuya-auth/device-sharing-session.json";
let yt=null,ys=null;
let tuya={userCode:null,qr:null,token:null,endpoint:null,terminal:null,username:null,devices:new Map(),homes:[],refreshing:false,sessionSource:null};
function out(id,ok,result,error){process.stdout.write("MONIK_RESP "+JSON.stringify({id,ok,result:result??null,error:error??null})+"\\n")}
function http(method,url,headers={},body,timeout=60000){return new Promise(resolve=>{let u;try{u=new URL(url)}catch(e){return resolve({ok:false,error:String(e),url})}let p=null,h={...headers};if(body!==undefined){p=Buffer.from(JSON.stringify(body));h["Content-Type"]="application/json";h["Content-Length"]=String(p.length)}let q=https.request({hostname:u.hostname,port:u.port||443,path:u.pathname+u.search,method,headers:h,timeout},r=>{let a=[];r.on("data",c=>a.push(c));r.on("end",()=>{let raw=Buffer.concat(a).toString("utf8"),j=null;try{j=JSON.parse(raw)}catch{}resolve({ok:r.statusCode>=200&&r.statusCode<300,http_status:r.statusCode,url,headers:r.headers,json:j,raw_body:raw})})});q.on("timeout",()=>q.destroy(new Error("timeout")));q.on("error",e=>resolve({ok:false,error:String(e),url}));if(p)q.write(p);q.end()})}
function env(path){let o={};try{for(let raw of fs.readFileSync(path,"utf8").split(/\r?\n/)){let s=raw.trim();if(!s||s.startsWith("#")||!s.includes("="))continue;let i=s.indexOf("="),k=s.slice(0,i).trim(),v=s.slice(i+1).trim();if((v.startsWith('"')&&v.endsWith('"'))||(v.startsWith("'")&&v.endsWith("'")))v=v.slice(1,-1);o[k]=v}}catch{}return o}
function token(v){if(typeof v==="string"){let s=v.trim();return s.length>20&&!/\s/.test(s)?s:null}if(Array.isArray(v)){for(let x of v){let t=token(x);if(t)return t}}else if(v&&typeof v==="object"){for(let k of ["access_token","accessToken","oauth_token","oauthToken","yandex_token","yandexToken","token"]){if(k in v){let t=token(v[k]);if(t)return t}}for(let x of Object.values(v)){let t=token(x);if(t)return t}}return null}
function loadY(){if(yt)return;for(let p of ["/opt/monik-yandex/data/yandex/token.json","/opt/monik-yandex/data/yandex/tokens.json","/opt/monik-yandex/data/yandex/oauth.json","/opt/monik-yandex/data/token.json","/opt/monik-yandex/token.json"]){try{let t=token(JSON.parse(fs.readFileSync(p,"utf8")));if(t){yt=t;ys=p;return}}catch{}}let rows=[];for(let p of ["/opt/monik-yandex/.env","/opt/monik-server-next/app/.env"]){for(let [k,v] of Object.entries(env(p)))if(String(v).length>20)rows.push({p,k,v})}for(let r of rows){let u=r.k.toUpperCase();if(u.includes("YANDEX")&&u.includes("TOKEN")){yt=r.v;ys=r.p+":"+r.k;return}}for(let r of rows)if(r.k.toUpperCase().includes("TOKEN")){yt=r.v;ys=r.p+":"+r.k;return}throw Error("No usable Yandex OAuth token")}
async function yAction(payload){loadY();return await http("POST",YBASE+"/devices/actions",{"Authorization":"Bearer "+yt,"Accept":"application/json","Content-Type":"application/json","Cache-Control":"no-cache"},payload)}
function nonce(n=12){let c="ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678",s="";for(let i=0;i<n;i++)s+=c[crypto.randomInt(0,c.length)];return s}
function md5(s){return crypto.createHash("md5").update(Buffer.from(s)).digest("hex")}
function hmac(k,s){return crypto.createHmac("sha256",Buffer.from(k)).update(Buffer.from(s)).digest("hex")}
function secret(rid,sid,hk){let m=hk;if(sid){let e="";for(let i=0;i<Math.min(sid.length,16);i++)e+=sid[sid.charCodeAt(i)%16]||"";m+="_"+e}return hmac(rid,m).slice(0,16)}
function enc(text,key){let nt=nonce(12),n=Buffer.from(nt),c=crypto.createCipheriv("aes-128-gcm",Buffer.from(key),n),x=Buffer.concat([c.update(Buffer.from(text)),c.final()]),tag=c.getAuthTag();return n.toString("base64")+Buffer.concat([x,tag]).toString("base64")}
function dec(text,key){let r=Buffer.from(text,"base64"),n=r.subarray(0,12),a=r.subarray(12),x=a.subarray(0,a.length-16),tag=a.subarray(a.length-16),d=crypto.createDecipheriv("aes-128-gcm",Buffer.from(key),n);d.setAuthTag(tag);return Buffer.concat([d.update(x),d.final()]).toString("utf8")}
function sign(hk,q,b,h){let p=[];for(let n of ["X-appKey","X-requestId","X-sid","X-time","X-token"])if(h[n])p.push(n+"="+h[n]);return hmac(hk,p.join("||")+(q||"")+(b||""))}
function connected(){return !!(tuya.token&&tuya.token.access_token&&tuya.token.refresh_token&&tuya.endpoint&&tuya.terminal)}
function normalizeStoredSession(s){if(!s||typeof s!=="object")return null;let t=s.token_info||s.token||{},u=String(s.user_code||s.userCode||"").trim(),terminal=String(s.terminal_id||s.terminal||"").trim(),endpoint=String(s.endpoint||"").trim();let token={t:t.t,uid:t.uid,expire_time:t.expire_time??t.expireTime,access_token:t.access_token??t.accessToken,refresh_token:t.refresh_token??t.refreshToken};if(!u||!terminal||!endpoint||!token.access_token||!token.refresh_token)return null;return {userCode:u,terminal,endpoint,token,username:s.username||null}}
function loadStoredSession(){try{let s=normalizeStoredSession(JSON.parse(fs.readFileSync(TUYA_SESSION_FILE,"utf8")));if(!s)return false;tuya={userCode:s.userCode,qr:null,token:s.token,endpoint:s.endpoint,terminal:s.terminal,username:s.username,devices:new Map(),homes:[],refreshing:false,sessionSource:"stored_strato_session"};return true}catch{return false}}
function saveStoredSession(reason){if(!connected())throw Error("Cannot save incomplete Tuya sharing session");let s={client_id:CLIENT,schema:SCHEMA,user_code:tuya.userCode,terminal_id:tuya.terminal,endpoint:tuya.endpoint,token_info:{t:tuya.token.t,uid:tuya.token.uid,expire_time:tuya.token.expire_time,access_token:tuya.token.access_token,refresh_token:tuya.token.refresh_token},username:tuya.username,updated_utc:new Date().toISOString(),update_reason:reason||"runtime"};let dir=TUYA_SESSION_FILE.slice(0,TUYA_SESSION_FILE.lastIndexOf("/")),tmp=TUYA_SESSION_FILE+".tmp";fs.mkdirSync(dir,{recursive:true});fs.writeFileSync(tmp,JSON.stringify(s,null,2),{encoding:"utf8",mode:0o600});fs.chmodSync(tmp,0o600);fs.renameSync(tmp,TUYA_SESSION_FILE);fs.chmodSync(TUYA_SESSION_FILE,0o600);tuya.sessionSource="stored_strato_session"}
async function ensureConnected(){if(!connected()&&!loadStoredSession())throw Error("No valid stored Tuya sharing session on MoniK server. Use QR only if the previous sharing was revoked or the session file is missing.");await refreshAccessToken(false);return true}
function expiryMs(){return Number(tuya.token?.t||0)+Number(tuya.token?.expire_time||0)*1000}
async function treqRaw(method,path,params,body,allowExpired=false){if(!connected())throw Error("Tuya shared account is not connected in this running session");let rid=crypto.randomUUID(),sid="",hk=md5(rid+String(tuya.token.refresh_token||"")),sec=secret(rid,sid,hk),q="",b="",url=String(tuya.endpoint).replace(/\/+$/,'')+path;if(params&&Object.keys(params).length){q=enc(JSON.stringify(params),sec);url+=(url.includes("?")?"&":"?")+"encdata="+encodeURIComponent(q)}let rb;if(body&&Object.keys(body).length){b=enc(JSON.stringify(body),sec);rb={encdata:b}}let h={"X-appKey":CLIENT,"X-requestId":rid,"X-sid":sid,"X-time":String(Date.now()),"X-token":tuya.token.access_token};h["X-sign"]=sign(hk,q,b,h);let r=await http(method,url,h,rb);if(!r.ok||!r.json)throw Error("Tuya HTTP request failed: "+JSON.stringify({http_status:r.http_status,error:r.error,body:r.raw_body}));let j={...r.json};if(j.result){try{let plain=dec(j.result,sec);try{j.result=JSON.parse(plain)}catch{j.result=plain}}catch(e){throw Error("Tuya response decrypt failed: "+String(e))}}if(j.success===false)throw Error("Tuya API "+String(j.code||"")+": "+String(j.msg||"unknown error"));return j}
async function refreshAccessToken(force=false){if(!connected())throw Error("Tuya shared account is not connected");if(tuya.refreshing)return;let left=expiryMs()-Date.now();if(!force&&left>60000)return;tuya.refreshing=true;try{let old=String(tuya.token.refresh_token||"");let j=await treqRaw("GET","/v1.0/m/token/"+encodeURIComponent(old),null,null,true),r=j.result||{};tuya.token={t:j.t,uid:r.uid,expire_time:r.expireTime,access_token:r.accessToken,refresh_token:r.refreshToken};if(!tuya.token.access_token||!tuya.token.refresh_token)throw Error("Tuya token refresh returned incomplete credentials");saveStoredSession("token_refresh")}finally{tuya.refreshing=false}}
async function treq(method,path,params,body){await refreshAccessToken(false);return await treqRaw(method,path,params,body)}
async function mapLimit(items,limit,fn){let out=new Array(items.length),next=0;async function worker(){while(true){let i=next++;if(i>=items.length)return;out[i]=await fn(items[i],i)}}await Promise.all(Array.from({length:Math.min(limit,items.length||1)},worker));return out}
async function loadAccount(){await ensureConnected();let h=await treq("GET","/v1.0/m/life/users/homes",null,null),homes=Array.isArray(h.result)?h.result:[];tuya.homes=homes;let lists=await mapLimit(homes,4,async home=>{let id=String(home.ownerId??home.id??"");if(!id)return[];let r=await treq("GET","/v1.0/m/life/ha/home/devices",{homeId:id},null);return Array.isArray(r.result)?r.result:[]});let unique=new Map();for(let list of lists)for(let d of list){let id=String(d.id??d.deviceId??d.devId??"");if(id&&!unique.has(id))unique.set(id,d)}let base=[...unique.values()];let enriched=await mapLimit(base,6,async d=>{let id=String(d.id??d.deviceId??d.devId??"");let spec={functions:[],status:[]};try{let r=await treq("GET","/v1.1/m/life/"+encodeURIComponent(id)+"/specifications",null,null);if(r&&r.result)spec=r.result}catch(e){spec={functions:[],status:[],spec_error:String(e)}}return {id,deviceId:id,name:d.name,local_key:d.local_key??d.localKey??null,category:d.category??null,product_id:d.product_id??d.productId??d.productKey??null,product_name:d.product_name??d.productName??null,online:d.online,ip:d.ip??null,uuid:d.uuid??null,sub:d.sub??false,icon:d.icon??null,protocolVersion:d.protocolVersion??d.version??null,status:Array.isArray(d.status)?d.status:(d.status||{}),specifications:{functions:Array.isArray(spec.functions)?spec.functions:[],status:Array.isArray(spec.status)?spec.status:[]}}});tuya.devices=new Map(enriched.map(d=>[d.id,d]));return {username:tuya.username,device_count:enriched.length,devices:enriched,home_count:homes.length}}
async function qrStart(code){tuya={userCode:String(code||'').trim(),qr:null,token:null,endpoint:null,terminal:null,username:null,devices:new Map(),homes:[],refreshing:false,sessionSource:"new_qr_pending"};if(!tuya.userCode)throw Error("Tuya User Code is empty");let url="https://"+LOGIN+"/v1.0/m/life/home-assistant/qrcode/tokens?clientid="+encodeURIComponent(CLIENT)+"&usercode="+encodeURIComponent(tuya.userCode)+"&schema="+encodeURIComponent(SCHEMA),r=await http("POST",url);if(!r.ok||!r.json||!r.json.success)throw Error("Tuya QR token request failed: "+JSON.stringify(r));tuya.qr=String((r.json.result||{}).qrcode||"");if(!tuya.qr)throw Error("Tuya returned no QR token");return {success:true,qr_payload:"tuyaSmart--qrLogin?token="+tuya.qr,session_persisted:false}}
async function qrPoll(){if(!tuya.qr||!tuya.userCode)throw Error("QR authorization was not started");let url="https://"+LOGIN+"/v1.0/m/life/home-assistant/qrcode/tokens/"+encodeURIComponent(tuya.qr)+"?clientid="+encodeURIComponent(CLIENT)+"&usercode="+encodeURIComponent(tuya.userCode),r=await http("GET",url);if(r.ok&&r.json&&r.json.success){let i={...(r.json.result||{}),t:r.json.t};tuya.token={t:i.t,uid:i.uid,expire_time:i.expire_time,access_token:i.access_token,refresh_token:i.refresh_token};tuya.endpoint=i.endpoint;tuya.terminal=i.terminal_id;tuya.username=i.username||null;if(!connected())throw Error("Tuya authorization returned incomplete session");tuya.sessionSource="new_qr_login";saveStoredSession("new_qr_login");let account=await loadAccount();return {approved:true,username:tuya.username,endpoint:tuya.endpoint,session_persisted:true,session_file:TUYA_SESSION_FILE,account}}let b=r.json||{};return {approved:false,code:b.code||null,msg:b.msg||null,http_status:r.http_status||null}}
async function sendTuyaCommand(deviceId,commands){await ensureConnected();if(!deviceId)throw Error("Tuya deviceId missing");if(!Array.isArray(commands)||!commands.length)throw Error("Tuya commands missing");let command_response=await treq("POST","/v1.1/m/thing/"+encodeURIComponent(deviceId)+"/commands",null,{commands});return {success:true,device_id:deviceId,commands,command_response,session_source:tuya.sessionSource,session_file:TUYA_SESSION_FILE}}
async function handle(c){if(c.op==="status"){if(!connected())loadStoredSession();return {ready:true,tuya_connected:connected(),tuya_session_source:tuya.sessionSource,tuya_session_file:TUYA_SESSION_FILE,tuya_username:tuya.username,tuya_devices:tuya.devices.size,yandex_token_loaded:!!yt,yandex_token_source:ys,strato_session_file_updates_only:true,strato_installs:false}}if(c.op==="yandex_action")return await yAction(c.payload);if(c.op==="tuya_qr_start")return await qrStart(c.user_code);if(c.op==="tuya_qr_poll")return await qrPoll();if(c.op==="tuya_account")return await loadAccount();if(c.op==="tuya_command")return await sendTuyaCommand(String(c.device_id||""),Array.isArray(c.commands)?c.commands:[]);throw Error("Unknown op "+c.op)}
const rl=readline.createInterface({input:process.stdin,crlfDelay:Infinity});process.stdout.write("MONIK_READY\\n");rl.on("line",async line=>{let c=null;try{c=JSON.parse(line);out(c.id,true,await handle(c),null)}catch(e){out(c&&c.id,false,null,String(e&&e.stack?e.stack:e))}});
'''


def txt(v: Any) -> str:
    return str(v).strip() if v is not None else ""


def first(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def sd(v: Any) -> dict:
    return v if isinstance(v, dict) else {}


def sl(v: Any) -> list:
    return v if isinstance(v, list) else []


def is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except Exception:
        return False


def strip_suffix(value: str) -> str:
    for suffix in KNOWN_SUFFIXES:
        if value.endswith(suffix):
            return value[:-len(suffix)]
    return value


def private_ip(value: Any) -> str | None:
    try:
        ip = ipaddress.ip_address(txt(value))
        return str(ip) if ip.is_private else None
    except Exception:
        return None


def public_ip(value: Any) -> str | None:
    try:
        ip = ipaddress.ip_address(txt(value))
        return str(ip) if not ip.is_private else None
    except Exception:
        return None



def find_private_ip_deep(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in (
            "lan_ip", "local_ip", "localIp", "last_ip", "lastIp",
            "ip_address", "ipAddress", "address", "ip"
        ):
            if key in value:
                found = private_ip(value.get(key))
                if found:
                    return found
        for child in value.values():
            found = find_private_ip_deep(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_private_ip_deep(child)
            if found:
                return found
    elif isinstance(value, str):
        match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", value)
        if match:
            return private_ip(match.group(0))
    return None


def find_mac_deep(value: Any) -> str | None:
    """Return the first exact MAC address found anywhere in one record."""
    if isinstance(value, dict):
        preferred = (
            "mac", "mac_address", "macAddress", "mac_addr",
            "wifi_mac", "wifiMac", "bssid"
        )
        for key in preferred:
            if key in value:
                found = norm_mac(value.get(key))
                if found:
                    return found
        for child in value.values():
            found = find_mac_deep(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_mac_deep(child)
            if found:
                return found
    elif isinstance(value, str):
        found = norm_mac(value)
        if found:
            return found
    return None

def parse_schema(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            pass
    return {}


def score(record: dict) -> int:
    keys = set(record)
    result = 3 if keys.intersection(ID_KEYS) else 0
    result += min(8, len(keys.intersection(HINT_KEYS)))
    if "capabilities" in keys and ("external_id" in keys or txt(record.get("type")).startswith("devices.types.")):
        result += 4
    if "function" in keys or "functions" in keys:
        result += 3
    if "code" in keys and not keys.intersection(ID_KEYS) and len(keys) < 9:
        result -= 5
    return result


def candidates(value: Any, path: str = "$", depth: int = 0, seen=None, out=None):
    if seen is None:
        seen = set()
    if out is None:
        out = []
    if depth > 30:
        return out
    if isinstance(value, dict):
        if id(value) in seen:
            return out
        seen.add(id(value))
        s = score(value)
        if s >= 5:
            out.append({"path": path, "score": s, "record": value})
        for key, nested in value.items():
            if isinstance(nested, (dict, list)):
                candidates(nested, path + "." + str(key), depth + 1, seen, out)
    elif isinstance(value, list):
        if id(value) in seen:
            return out
        seen.add(id(value))
        for i, nested in enumerate(value):
            if isinstance(nested, (dict, list)):
                candidates(nested, f"{path}[{i}]", depth + 1, seen, out)
    return out


def identity(record: dict, yid_to_external: dict[str, str] | None = None) -> dict:
    raw_id = txt(record.get("id"))
    yid = txt(record.get("yandex_id"))
    ext = txt(first(record.get("external_id"), record.get("external_device_id")))
    tid = txt(first(record.get("deviceId"), record.get("device_id"), record.get("devId"), record.get("dev_id")))
    ylike = bool(ext or record.get("skill_id") or txt(record.get("type")).startswith("devices.types.") or (isinstance(record.get("capabilities"), list) and is_uuid(raw_id)))
    tlike = bool(record.get("local_key") or record.get("localKey") or record.get("product_id") or record.get("productId") or record.get("category") or record.get("function") or record.get("status_range") or record.get("local_strategy"))
    if not yid and ylike and is_uuid(raw_id):
        yid = raw_id
    if not ext and yid and yid_to_external:
        ext = txt(yid_to_external.get(yid))
    if not tid and tlike and raw_id and not is_uuid(raw_id):
        tid = raw_id
    if tid.startswith("tuya:"):
        tid = tid[5:]
    fallback_raw = raw_id
    if fallback_raw.startswith("tuya:"):
        fallback_raw = fallback_raw[5:]
    pid = tid or strip_suffix(ext) or (fallback_raw if fallback_raw and not is_uuid(fallback_raw) else "") or yid
    return {"raw_id": raw_id, "yandex_id": yid, "external_id": ext, "tuya_id": tid, "physical_id": pid}


def status_map(record: dict) -> dict:
    out = {}
    def consume(v):
        if isinstance(v, dict):
            for k, x in v.items():
                if k not in {"result", "success", "functions", "status", "status_range"}:
                    out.setdefault(str(k), x)
        elif isinstance(v, list):
            for row in v:
                if isinstance(row, dict) and "value" in row:
                    c = first(row.get("code"), row.get("statusCode"), row.get("status_code"))
                    if c is not None:
                        out[str(c)] = row.get("value")
    consume(record.get("status")); consume(record.get("dps")); consume(sd(record.get("specifications")).get("status"))
    return out


def dp_map(record: dict) -> tuple[dict[str, int], dict[str, str]]:
    """
    Build exact code -> numeric DP ID mappings from every explicit schema field.

    This function never guesses DP IDs from order, names, or conventional defaults.
    """
    out: dict[str, int] = {}
    evidence: dict[str, str] = {}

    def put(code: Any, dp: Any, source: str) -> None:
        if code is None or dp is None:
            return
        try:
            dp_id = int(dp)
        except Exception:
            return
        if dp_id < 1 or dp_id > 10000:
            return
        code_text = str(code)
        if code_text not in out:
            out[code_text] = dp_id
            evidence[code_text] = source

    local_strategy = record.get("local_strategy")
    if isinstance(local_strategy, dict):
        for dp_id, row in local_strategy.items():
            if not isinstance(row, dict):
                continue
            put(
                first(row.get("status_code"), row.get("statusCode"), row.get("code")),
                dp_id,
                "local_strategy",
            )

    def consume_rows(value: Any, source: str, allow_plain_id: bool = False) -> None:
        if isinstance(value, dict):
            for key, row in value.items():
                if isinstance(row, dict):
                    merged = dict(row)
                    merged.setdefault("code", key)
                    consume_rows([merged], source, allow_plain_id)
        elif isinstance(value, list):
            for row in value:
                if not isinstance(row, dict):
                    continue
                code = first(
                    row.get("statusCode"), row.get("status_code"), row.get("code")
                )
                dp_id = first(row.get("dpId"), row.get("dp_id"), row.get("dpid"))
                if dp_id is None and allow_plain_id:
                    # "id" is accepted only inside known schema/function/status arrays.
                    dp_id = row.get("id")
                put(code, dp_id, source)

    status_strategy = sd(record.get("status_strategy"))
    strategy_result = sd(status_strategy.get("result"))
    for rows, source in (
        (record.get("dpStatusRelationDTOS"), "dpStatusRelationDTOS"),
        (status_strategy.get("dpStatusRelationDTOS"), "status_strategy.dpStatusRelationDTOS"),
        (strategy_result.get("dpStatusRelationDTOS"), "status_strategy.result.dpStatusRelationDTOS"),
    ):
        consume_rows(rows, source, False)

    specifications = sd(record.get("specifications"))
    for rows, source in (
        (record.get("function"), "function.explicit_dp"),
        (record.get("functions"), "functions.explicit_dp"),
        (record.get("status"), "status.explicit_dp"),
        (record.get("status_range"), "status_range.explicit_dp"),
        (record.get("statusRange"), "statusRange.explicit_dp"),
        (specifications.get("functions"), "specifications.functions.explicit_dp"),
        (specifications.get("status"), "specifications.status.explicit_dp"),
        (record.get("schema"), "schema.explicit_dp"),
        (record.get("schemaInfo"), "schemaInfo.explicit_dp"),
        (record.get("schema_info"), "schema_info.explicit_dp"),
    ):
        consume_rows(rows, source, True)

    return out, evidence



CHANNEL_COUNT_KEYS = (
    "channel_count", "channelCount", "channels_count", "channelsCount",
    "switch_count", "switchCount", "gang_count", "gangCount",
    "gang", "gangs", "channel_num", "channelNum",
    "outlet_count", "outletCount", "socket_count", "socketCount",
    "way_count", "wayCount",
)


def positive_channel_count(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        count = int(value)
        return count if 1 <= count <= 32 else 0
    if isinstance(value, str):
        match = re.search(r"\b([1-9]|[12]\d|3[0-2])\b", value)
        return int(match.group(1)) if match else 0
    if isinstance(value, list):
        count = len(value)
        return count if 1 <= count <= 32 else 0
    return 0


def schema_channel_count(record: dict) -> tuple[int, str | None]:
    """
    Read channel/gang count from the manually selected JSON only.
    This is schema interpretation, never device correlation by name.
    """
    best = 0
    source = None

    def consider(value: Any, where: str) -> None:
        nonlocal best, source
        count = positive_channel_count(value)
        if count > best:
            best = count
            source = where

    def scan(value: Any, path: str, depth: int = 0) -> None:
        if depth > 8:
            return
        if isinstance(value, dict):
            for key, nested in value.items():
                key_text = str(key)
                if key_text in CHANNEL_COUNT_KEYS:
                    consider(nested, path + "." + key_text)
                if isinstance(nested, (dict, list)):
                    scan(nested, path + "." + key_text, depth + 1)
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                if isinstance(nested, (dict, list)):
                    scan(nested, f"{path}[{index}]", depth + 1)

    scan(record, "$")

    containers = [
        record.get("function"), record.get("functions"),
        record.get("status"), record.get("status_range"),
        record.get("statusRange"), record.get("schema"),
        record.get("schemaInfo"), record.get("schema_info"),
        sd(record.get("specifications")).get("functions"),
        sd(record.get("specifications")).get("status"),
    ]
    for container in containers:
        rows = list(container.values()) if isinstance(container, dict) else sl(container)
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = txt(first(
                row.get("code"), row.get("statusCode"), row.get("status_code")
            ))
            match = re.search(
                r"(?:^|_)(?:switch|switch_led|relay|channel|outlet|socket)_(\d+)$",
                code.lower(),
            )
            if match:
                consider(int(match.group(1)), "schema_code_suffix")

    external_id = txt(first(
        record.get("external_id"), record.get("external_device_id")
    ))
    match = re.search(r"_switch_(\d+)$", external_id)
    if match:
        consider(int(match.group(1)), "yandex_external_id_suffix")

    schema_text = " ".join(
        txt(record.get(key))
        for key in (
            "name", "product_name", "productName",
            "model", "category_name", "categoryName",
        )
    )
    for pattern in (
        r"\b([1-9]|[12]\d|3[0-2])\s*ch\b",
        r"\b([1-9]|[12]\d|3[0-2])\s*channels?\b",
        r"\b([1-9]|[12]\d|3[0-2])\s*gang\b",
        r"\b([1-9]|[12]\d|3[0-2])\s*way\b",
    ):
        match = re.search(pattern, schema_text, re.I)
        if match:
            consider(int(match.group(1)), "product_schema_text")

    return best, source


def control_channel_index(code: Any) -> int | None:
    match = re.search(r"_(\d+)$", txt(code))
    return int(match.group(1)) if match else None


def is_switch_control(control: dict) -> bool:
    code = txt(first(control.get("command_code"), control.get("code"))).lower()
    return bool(
        control.get("kind") == "boolean"
        and re.search(
            r"(^|_)(switch|switch_led|relay|power|outlet|socket)(_|$)",
            code,
        )
    )


def inferred_channel_code(base_code: Any, index: int) -> str:
    base = txt(base_code) or "switch"
    match = re.match(r"^(.*?)(?:_\d+)?$", base)
    prefix = match.group(1) if match else base
    return f"{prefix}_{index}"


def expand_multichannel_schema(group: dict, controls: list[dict]) -> list[dict]:
    """
    Build every logical channel declared by the selected JSON schema.

    If the JSON declares multiple channels but contains only one command code,
    every channel is built and uses that one shared command code. No new
    numeric DP ID is invented.
    """
    channel_count = int(group.get("channel_count") or 0)
    exact_switches = [
        control for control in controls
        if not control.get("virtual")
        and not txt(control.get("code")).startswith("yandex:")
        and is_switch_control(control)
    ]

    indexes = [
        control_channel_index(control.get("code"))
        for control in exact_switches
    ]
    indexes = [value for value in indexes if value is not None]
    if indexes:
        channel_count = max(channel_count, max(indexes))

    endpoint_indexes = []
    for endpoint in group.get("endpoints", []):
        match = re.search(r"_switch_(\d+)$", txt(endpoint.get("external_id")))
        if match:
            endpoint_indexes.append(int(match.group(1)))
    if endpoint_indexes:
        channel_count = max(channel_count, max(endpoint_indexes))

    for control in exact_switches:
        control.setdefault("command_code", control.get("code"))
        control.setdefault("schema_inferred", False)
        control["channel_index"] = control_channel_index(control.get("code"))
        control["channel_count"] = channel_count or 1

    if channel_count <= 1:
        return controls

    by_index = {
        control["channel_index"]: control
        for control in exact_switches
        if control.get("channel_index") is not None
    }

    shared = exact_switches[0] if len(exact_switches) == 1 else None
    if shared is None:
        shared = next(
            (
                control for control in exact_switches
                if control.get("channel_index") is None
            ),
            None,
        )

    for index in range(1, channel_count + 1):
        if index in by_index:
            continue

        command_code = shared.get("command_code") if shared else None
        shared_dp_id = shared.get("dp_id") if shared else None
        synthetic_code = inferred_channel_code(
            shared.get("code") if shared else "switch",
            index,
        )

        control = {
            "code": synthetic_code,
            "command_code": command_code,
            "name": f"Channel {index}",
            "description": (
                f"Logical channel {index} built from the selected JSON schema. "
                + (
                    f"It uses the single available command code {command_code}."
                    if command_code
                    else "No direct command code is present in the selected JSON."
                )
            ),
            "type": "Boolean",
            "kind": "boolean",
            "values": {},
            "current": shared.get("current") if shared else None,
            "controllable": True,
            "dp_id": shared_dp_id,
            "dp_source": (
                "shared_single_selected_json_code"
                if shared_dp_id is not None
                else None
            ),
            "dp_confidence": (
                "shared_from_selected_json"
                if command_code
                else "no_direct_code_in_selected_json"
            ),
            "schema_inferred": True,
            "shared_command_code": bool(command_code),
            "channel_index": index,
            "channel_count": channel_count,
            "virtual": False,
            "virtual_actions": [],
            "yandex_actions": yactions(
                synthetic_code,
                {"type": "Boolean", "values": {}},
                group.get("endpoints", []),
            ),
        }
        control["routes"] = {
            "model": True,
            "local": False,
            "tuya_cloud": bool(group.get("tuya_id") and command_code),
            "yandex": bool(control["yandex_actions"]),
        }
        controls.append(control)
        by_index[index] = control

    return controls


def numeric_schema(row: dict) -> dict:
    values = sd(first(row.get("values"), row.get("valueRange"), row.get("value_range")))
    def num(*items):
        for item in items:
            if isinstance(item, (int, float)) and not isinstance(item, bool):
                return item
            if isinstance(item, str):
                try:
                    return float(item) if "." in item else int(item)
                except Exception:
                    pass
        return None
    return {
        "min": num(row.get("min"), values.get("min")),
        "max": num(row.get("max"), values.get("max")),
        "step": num(row.get("step"), values.get("step")),
        "scale": num(row.get("scale"), values.get("scale"), 0) or 0,
        "unit": first(row.get("unit"), values.get("unit")),
    }


def coerce_control_value(control: dict, value: Any) -> Any:
    if control.get("kind") not in ("integer", "number", "range"):
        return value
    schema = control.get("numeric_schema") or {}
    minimum = schema.get("min")
    maximum = schema.get("max")
    step = schema.get("step")
    try:
        number = float(value)
    except Exception:
        return value
    if minimum is not None:
        number = max(float(minimum), number)
    if maximum is not None:
        number = min(float(maximum), number)
    if step not in (None, 0):
        base = float(minimum or 0)
        number = base + round((number - base) / float(step)) * float(step)
    return int(number) if float(number).is_integer() else number


def functions(record: dict) -> dict:
    out = {}
    def add(row, source, controllable):
        if not isinstance(row, dict): return
        code = first(row.get("code"), row.get("statusCode"), row.get("status_code"))
        if code is None: return
        code = str(code)
        item = out.setdefault(code, {"code": code, "name": None, "description": None, "type": None, "values": {}, "controllable": False})
        item["name"] = first(item["name"], row.get("name")); item["description"] = first(item["description"], row.get("desc"), row.get("description")); item["type"] = first(item["type"], row.get("type"), row.get("valueType")); item["values"].update(parse_schema(first(row.get("values"), row.get("valueDesc"), row.get("schema")))); item["controllable"] = bool(item["controllable"] or controllable)
    def consume(v, source, controllable):
        if isinstance(v, dict):
            for k, row in v.items():
                if isinstance(row, dict):
                    row = dict(row); row.setdefault("code", k); add(row, source, controllable)
        elif isinstance(v, list):
            for row in v: add(row, source, controllable)
    consume(record.get("function"), "function", True); consume(record.get("functions"), "functions", True)
    spec = sd(record.get("specifications")); consume(spec.get("functions"), "specifications.functions", True); consume(spec.get("status"), "specifications.status", False)
    consume(record.get("status_range"), "status_range", False); consume(record.get("statusRange"), "statusRange", False)
    for code in sl(record.get("codeNames")):
        out.setdefault(str(code), {"code": str(code), "name": None, "description": None, "type": None, "values": {}, "controllable": False})
    st = status_map(record)
    for code, value in st.items():
        item = out.setdefault(code, {"code": code, "name": None, "description": None, "type": None, "values": {}, "controllable": False})
        if item["type"] is None:
            item["type"] = "Boolean" if isinstance(value, bool) else "Integer" if isinstance(value, (int, float)) and not isinstance(value, bool) else "Json" if isinstance(value, (dict, list)) else "String"
    return out


def ycaps(record: dict) -> list:
    out, seen = [], set()
    for cap in sl(record.get("capabilities")):
        if not isinstance(cap, dict) or not cap.get("type"): continue
        p, s = sd(cap.get("parameters")), sd(cap.get("state")); key = json.dumps([cap.get("type"), first(p.get("instance"), s.get("instance")), s], sort_keys=True, ensure_ascii=False)
        if key in seen: continue
        seen.add(key); out.append({"type": cap.get("type"), "parameters": p, "state": s, "retrievable": cap.get("retrievable"), "reportable": cap.get("reportable")})
    return out


def kind(fn: dict, current: Any) -> str:
    t = txt(fn.get("type")).lower(); schema = sd(fn.get("values"))
    if t in ("boolean", "bool") or isinstance(current, bool): return "boolean"
    if t in ("integer", "value", "float", "number") or (isinstance(current, (int, float)) and not isinstance(current, bool)): return "number"
    if t == "enum" or isinstance(schema.get("range"), list): return "enum"
    if t in ("json", "raw"): return "json"
    if t == "string" or isinstance(current, str): return "string"
    return "unknown"


def yactions(code: str, fn: dict, endpoints: list) -> list:
    out, lower = [], code.lower()
    switch = bool(re.search(r"(^switch($|_)|switch_led|power|light$|fan_switch)", lower))
    bright = "bright" in lower
    code_channel_match = re.search(r"_(\d+)$", lower)
    code_channel = code_channel_match.group(1) if code_channel_match else None
    for ep in endpoints:
        external_id = txt(ep.get("external_id"))
        endpoint_channel_match = re.search(r"_switch_(\d+)$", external_id)
        endpoint_channel = endpoint_channel_match.group(1) if endpoint_channel_match else None

        # Never map one base Yandex endpoint to several Tuya channels.
        # A channel code is mapped only to an explicitly matching _switch_N endpoint.
        if code_channel:
            if endpoint_channel != code_channel:
                continue
        elif endpoint_channel:
            continue

        for cap in ep.get("capabilities", []):
            short = txt(cap.get("type")).rsplit(".", 1)[-1]
            p, state = sd(cap.get("parameters")), sd(cap.get("state"))
            inst = first(p.get("instance"), state.get("instance"), "on" if short == "on_off" else None)
            if short == "on_off" and switch:
                out.append({"device_id": ep.get("yandex_id"), "type": cap.get("type"), "instance": inst or "on", "endpoint_name": ep.get("name"), "external_id": external_id})
            elif short == "range" and bright and inst == "brightness":
                out.append({"device_id": ep.get("yandex_id"), "type": cap.get("type"), "instance": "brightness", "endpoint_name": ep.get("name"), "external_id": external_id})
    return out


def yandex_controls(endpoints: list) -> list:
    controls = []
    seen = set()
    for endpoint in endpoints:
        yid = txt(endpoint.get("yandex_id"))
        if not yid:
            continue
        endpoint_name = first(endpoint.get("name"), endpoint.get("external_id"), yid)
        for cap in endpoint.get("capabilities", []):
            cap_type = txt(cap.get("type"))
            if not cap_type:
                continue
            short = cap_type.rsplit(".", 1)[-1]
            parameters = sd(cap.get("parameters"))
            state = sd(cap.get("state"))
            instance = first(
                parameters.get("instance"),
                state.get("instance"),
                "on" if short == "on_off" else
                "get_stream" if short == "video_stream" else short,
            )
            key = (yid, cap_type, txt(instance))
            if key in seen:
                continue
            seen.add(key)

            current = state.get("value")
            values = {}
            control_kind = "json"
            if short in ("on_off", "toggle"):
                control_kind = "boolean"
            elif short == "range":
                control_kind = "number"
                values = sd(parameters.get("range")).copy()
                if parameters.get("precision") is not None:
                    values["precision"] = parameters.get("precision")
            elif short == "mode":
                control_kind = "enum"
                modes = parameters.get("modes")
                if isinstance(modes, list):
                    values["range"] = [
                        row.get("value")
                        for row in modes
                        if isinstance(row, dict) and row.get("value") is not None
                    ]
            elif short == "color_setting":
                control_kind = "json"
                if current is None:
                    current = {
                        "instance": instance,
                        "value": None,
                    }
            elif short == "video_stream":
                control_kind = "json"
                if current is None:
                    current = {
                        "instance": "get_stream",
                        "value": {"protocols": ["hls"]},
                    }

            controls.append({
                "code": f"yandex:{yid}:{short}:{instance}",
                "name": f"{endpoint_name} — {short}"
                    + (f" / {instance}" if instance else ""),
                "description": "Control built directly from the exact Yandex capability schema.",
                "type": cap_type,
                "kind": control_kind,
                "values": values,
                "current": current,
                "controllable": True,
                "dp_id": None,
                "virtual": False,
                "virtual_actions": [],
                "yandex_actions": [{
                    "device_id": yid,
                    "type": cap_type,
                    "instance": instance,
                    "endpoint_name": endpoint_name,
                    "external_id": endpoint.get("external_id"),
                }],
                "routes": {
                    "model": True,
                    "local": False,
                    "tuya_cloud": False,
                    "yandex": True,
                },
            })
    return controls


def build(raw: Any, source: str) -> dict:
    groups = {}
    candidate_list = candidates(raw)
    yid_to_external = {}
    for cand in candidate_list:
        ident0 = identity(cand["record"])
        if ident0["yandex_id"] and ident0["external_id"]:
            yid_to_external.setdefault(ident0["yandex_id"], ident0["external_id"])
    for cand in candidate_list:
        record = cand["record"]
        ident = identity(record, yid_to_external)
        pid = ident["physical_id"]
        if not pid: continue
        g = groups.setdefault(pid, {"physical_id": pid, "tuya_id": None, "uuid": None, "node_id": None, "gateway_id": None, "parent_id": None, "name": None, "category": None, "product_id": None, "product_name": None, "manufacturer": None, "model": None, "online": None, "mac": None, "lan_ip": None, "external_ip": None, "local_key": None, "protocol_version": None, "status": {}, "functions": {}, "dp_map": {}, "dp_sources": {}, "endpoints": [], "record_count": 0, "channel_count": 0, "channel_count_sources": [], "warnings": []})
        g["record_count"] += 1; g["uuid"] = first(g["uuid"], record.get("uuid"), record.get("uuid_id"), record.get("uuidId")); g["node_id"] = first(g["node_id"], record.get("node_id"), record.get("nodeId")); g["gateway_id"] = first(g["gateway_id"], record.get("gateway_id"), record.get("gatewayId"), record.get("gw_id"), record.get("gwId")); g["parent_id"] = first(g["parent_id"], record.get("parent_id"), record.get("parentId")); _cc,_ccs=schema_channel_count(record); g["channel_count"]=max(g["channel_count"],_cc); g["channel_count_sources"].append(_ccs) if _ccs and _ccs not in g["channel_count_sources"] else None; g["tuya_id"] = first(g["tuya_id"], ident["tuya_id"], pid if not is_uuid(pid) else None); g["name"] = first(g["name"], record.get("name"), record.get("product_name"), record.get("productName")); g["category"] = first(g["category"], record.get("category")); g["product_id"] = first(g["product_id"], record.get("product_id"), record.get("productId")); g["product_name"] = first(g["product_name"], record.get("product_name"), record.get("productName")); info = sd(record.get("device_info")); g["manufacturer"] = first(g["manufacturer"], info.get("manufacturer"), record.get("manufacturer")); g["model"] = first(g["model"], info.get("model"), record.get("model")); g["online"] = first(g["online"], record.get("online")); g["mac"] = first(g["mac"], norm_mac(record.get("mac")), find_mac_deep(record)); ip = first(
            record.get("lan_ip"),
            record.get("local_ip"),
            record.get("localIp"),
            record.get("last_ip"),
            record.get("lastIp"),
            record.get("ip_address"),
            record.get("ipAddress"),
            record.get("address"),
            record.get("ip") if private_ip(record.get("ip")) else None,
            info.get("lan_ip"),
            info.get("local_ip"),
            info.get("last_ip"),
            info.get("ip"),
        ); g["lan_ip"] = first(g["lan_ip"], private_ip(ip)); ex = first(record.get("external_ip"), record.get("public_ip"), record.get("ip") if public_ip(record.get("ip")) else None); g["external_ip"] = first(g["external_ip"], public_ip(ex)); g["local_key"] = first(g["local_key"], record.get("local_key"), record.get("localKey")); g["protocol_version"] = first(g["protocol_version"], record.get("protocolVersion"), record.get("protocol_version"), record.get("version")); g["lan_ip"] = first(g["lan_ip"], find_private_ip_deep(record)); g["status"].update(status_map(record)); _dpm,_dps=dp_map(record); g["dp_map"].update(_dpm); g["dp_sources"].update(_dps)
        for code, fn in functions(record).items():
            old = g["functions"].setdefault(code, fn)
            if old is not fn:
                old["name"] = first(old.get("name"), fn.get("name")); old["description"] = first(old.get("description"), fn.get("description")); old["type"] = first(old.get("type"), fn.get("type")); old["values"] = {**sd(old.get("values")), **sd(fn.get("values"))}; old["controllable"] = bool(old.get("controllable") or fn.get("controllable"))
        if ident["yandex_id"]:
            ep = {"yandex_id": ident["yandex_id"], "external_id": ident["external_id"], "name": record.get("name"), "type": record.get("type"), "skill_id": record.get("skill_id"), "capabilities": ycaps(record), "properties": sl(record.get("properties"))}
            if not any(x.get("yandex_id") == ep["yandex_id"] and x.get("external_id") == ep["external_id"] for x in g["endpoints"]): g["endpoints"].append(ep)
    # Collapse duplicate UUID-only Yandex records into their exact external_id physical group.
    for old_pid in list(groups.keys()):
        if old_pid not in groups:
            continue
        src_group = groups[old_pid]
        target_pid = None
        if old_pid.startswith("tuya:"):
            target_pid = old_pid[5:]
        elif is_uuid(old_pid):
            bases = {
                strip_suffix(txt(endpoint.get("external_id")))
                for endpoint in src_group.get("endpoints", [])
                if txt(endpoint.get("external_id"))
            }
            if len(bases) == 1:
                target_pid = next(iter(bases))
        if not target_pid or target_pid == old_pid:
            continue

        dst = groups.get(target_pid)
        if dst is None:
            src_group["physical_id"] = target_pid
            groups[target_pid] = src_group
            del groups[old_pid]
            continue

        for field in ("tuya_id", "uuid", "node_id", "gateway_id", "parent_id", "name", "category", "product_id", "product_name",
                      "manufacturer", "model", "online", "mac", "lan_ip",
                      "external_ip", "local_key", "protocol_version"):
            dst[field] = first(dst.get(field), src_group.get(field))
        dst["record_count"] += src_group.get("record_count", 0)
        dst["channel_count"] = max(dst.get("channel_count", 0), src_group.get("channel_count", 0))
        for channel_source in src_group.get("channel_count_sources", []):
            if channel_source not in dst["channel_count_sources"]:
                dst["channel_count_sources"].append(channel_source)
        dst["status"].update(src_group.get("status", {}))
        dst["dp_map"].update(src_group.get("dp_map", {})); dst["dp_sources"].update(src_group.get("dp_sources", {}))
        for code, fn in src_group.get("functions", {}).items():
            old_fn = dst["functions"].setdefault(code, fn)
            if old_fn is not fn:
                old_fn["name"] = first(old_fn.get("name"), fn.get("name"))
                old_fn["description"] = first(old_fn.get("description"), fn.get("description"))
                old_fn["type"] = first(old_fn.get("type"), fn.get("type"))
                old_fn["values"] = {**sd(old_fn.get("values")), **sd(fn.get("values"))}
                old_fn["controllable"] = bool(old_fn.get("controllable") or fn.get("controllable"))
        for endpoint in src_group.get("endpoints", []):
            if not any(
                item.get("yandex_id") == endpoint.get("yandex_id")
                and item.get("external_id") == endpoint.get("external_id")
                for item in dst["endpoints"]
            ):
                dst["endpoints"].append(endpoint)
        for warning in src_group.get("warnings", []):
            if warning not in dst["warnings"]:
                dst["warnings"].append(warning)
        del groups[old_pid]

    devices=[]; controls_total=0; endpoint_total=0
    for pid, g in groups.items():
        g["name"] = g["name"] or g["product_name"] or pid; endpoint_total += len(g["endpoints"])
        if g["lan_ip"] and not g["local_key"]: g["warnings"].append("Private LAN IP exists, but localKey is missing.")
        if g["local_key"] and not g["lan_ip"]: g["warnings"].append("Local control data is complete; current LAN does not match this device.")
        if not g["functions"]: g["warnings"].append("No Tuya function/status schema was found in this JSON.")
        if not g["endpoints"]: g["warnings"].append("No Yandex logical endpoint was correlated.")
        controls=[]
        for code, fn in sorted(g["functions"].items()):
            current=g["status"].get(code); c={"code":code,"name":first(fn.get("name"),code),"description":fn.get("description"),"type":fn.get("type"),"kind":kind(fn,current),"values":fn.get("values") or {},"current":current,"controllable":bool(fn.get("controllable")),"dp_id":g["dp_map"].get(code),"dp_source":g["dp_sources"].get(code),"dp_confidence":"exact_selected_json" if g["dp_map"].get(code) is not None else "missing_in_selected_json","command_code":code,"schema_inferred":False,"shared_command_code":False,"numeric_schema":numeric_schema(fn),"virtual":False,"virtual_actions":[],"yandex_actions":yactions(code,fn,g["endpoints"])}; c["routes"]={"model":True,"local":False,"tuya_cloud":bool(g["tuya_id"] and c.get("command_code")),"yandex":bool(c["yandex_actions"])}; controls.append(c)
        controls=expand_multichannel_schema(g,controls)
        controls.extend(yandex_controls(g["endpoints"]))
        channels=[c for c in controls if not c.get("virtual") and not txt(c.get("code")).startswith("yandex:") and c.get("kind")=="boolean" and c.get("channel_index") is not None]
        if len(channels)>=2:
            m={"code":"__virtual_master_switch__","name":"Master — all channels","description":"Virtual master synthesized only from exact channel switch codes.","type":"Boolean","kind":"boolean","values":{},"current":None,"controllable":True,"dp_id":None,"dp_source":"derived_only_from_exact_selected_json_channels","dp_confidence":"derived_from_selected_json","virtual":True,"virtual_actions":[{"code":c.get("command_code"),"logical_code":c["code"],"dp_id":c["dp_id"]} for c in channels],"yandex_actions":[]}; m["routes"]={"model":True,"local":False,"tuya_cloud":bool(g["tuya_id"]),"yandex":False}; controls.insert(0,m)
        controls_total += len(controls); coverage={"records_found":g["record_count"],"tuya_schema_codes":len(g["functions"]),"dp_id_mappings":len(g["dp_map"]),"status_codes":len(g["status"]),"yandex_logical_endpoints":len(g["endpoints"]),"controls_built":len(controls),"local_route_ready":sum(1 for c in controls if c["routes"]["local"]),"tuya_cloud_route_ready":sum(1 for c in controls if c["routes"]["tuya_cloud"]),"yandex_route_ready":sum(1 for c in controls if c["routes"]["yandex"])}
        devices.append({"physical_id":pid,"tuya_id":g["tuya_id"],"name":g["name"],"category":g["category"],"product_id":g["product_id"],"product_name":g["product_name"],"manufacturer":g["manufacturer"],"model":g["model"],"online":g["online"],"mac":g["mac"],"lan_ip":g["lan_ip"],"external_ip":g["external_ip"],"has_local_key":bool(g["local_key"]),"local_key":g["local_key"],"protocol_version":txt(g["protocol_version"] or "3.3"),"logical_endpoints":g["endpoints"],"schema_channel_count":g["channel_count"],"schema_channel_count_sources":g["channel_count_sources"],"status":g["status"],"controls":controls,"coverage":coverage,"warnings":g["warnings"]})
    devices.sort(key=lambda d:(0 if d.get("lan_ip") else 1,txt(d.get("name")).lower(),d["physical_id"]))
    return {"source_name":source,"physical_device_count":len(devices),"logical_endpoint_count":endpoint_total,"control_count":controls_total,"devices":devices,"global_warnings":[] if devices else ["Valid JSON, but no device-like records were found."],"algorithm":{"version":"UNIVERSAL_MODEL_V1","name_matching_used":False,"archive_scanning_used":False,"identity_order":["exact Tuya deviceId/devId","Yandex external_id with known suffix removed","non-UUID id","Yandex UUID fallback"],"virtual_master_rule":"Only exact Boolean switch_N/switch_led_N channels","relay_status_used_as_master":False}}



def _recount_model(model: dict) -> None:
    devices = model.get("devices", [])
    model["physical_device_count"] = len(devices)
    model["control_count"] = sum(len(d.get("controls", [])) for d in devices)
    model["logical_endpoint_count"] = sum(len(d.get("logical_endpoints", [])) for d in devices)
    for d in devices:
        controls = d.get("controls", [])
        coverage = d.setdefault("coverage", {})
        coverage["controls_built"] = len(controls)
        coverage["local_route_ready"] = sum(1 for c in controls if c.get("routes", {}).get("local"))
        coverage["tuya_cloud_route_ready"] = sum(1 for c in controls if c.get("routes", {}).get("tuya_cloud"))
        coverage["yandex_route_ready"] = sum(1 for c in controls if c.get("routes", {}).get("yandex"))


def merge_tuya_account(model: dict, account: dict) -> dict:
    """Merge the manually shared Tuya account by exact deviceId only."""
    rows = account.get("devices") if isinstance(account, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Tuya account snapshot has no device list")

    account_model = build({"devices": rows}, "Tuya shared account")
    existing = model.setdefault("devices", [])
    by_exact: dict[str, dict] = {}
    for d in existing:
        for key in (txt(d.get("tuya_id")), txt(d.get("physical_id"))):
            if key:
                by_exact.setdefault(key, d)
        d["tuya_shared"] = False
        for c in d.get("controls", []):
            if txt(c.get("code")).startswith("yandex:"):
                continue
            command_code = txt(c.get("command_code") or c.get("code"))
            routes = c.setdefault("routes", {})
            routes["tuya_cloud"] = bool(
                routes.get("tuya_cloud")
                or (txt(d.get("tuya_id")) and command_code)
            )

    for incoming in account_model.get("devices", []):
        tid = txt(incoming.get("tuya_id") or incoming.get("physical_id"))
        target = by_exact.get(tid)
        if target is None:
            target = incoming
            existing.append(target)
            by_exact[tid] = target
        else:
            for field in ("tuya_id", "uuid", "node_id", "gateway_id", "parent_id", "name", "category", "product_id", "product_name",
                          "manufacturer", "model", "online", "mac", "protocol_version"):
                target[field] = first(incoming.get(field), target.get(field))
            target["local_key"] = first(incoming.get("local_key"), target.get("local_key"))
            target["has_local_key"] = bool(target.get("local_key"))
            target["status"] = {**sd(target.get("status")), **sd(incoming.get("status"))}
            if not target.get("lan_ip"):
                target["lan_ip"] = incoming.get("lan_ip")

            current_controls = {txt(c.get("code")): c for c in target.get("controls", [])}
            for inc in incoming.get("controls", []):
                code = txt(inc.get("code"))
                if not code or code.startswith("yandex:"):
                    continue
                old = current_controls.get(code)
                if old is None:
                    target.setdefault("controls", []).append(inc)
                    current_controls[code] = inc
                else:
                    for field in ("name", "description", "type", "kind", "values",
                                  "current", "controllable", "numeric_schema", "command_code"):
                        if inc.get(field) not in (None, "", {}, []):
                            old[field] = inc.get(field)

        target["tuya_shared"] = True
        target["tuya_id"] = tid
        for c in target.get("controls", []):
            if txt(c.get("code")).startswith("yandex:"):
                continue
            command_code = txt(c.get("command_code") or c.get("code"))
            routes = c.setdefault("routes", {})
            routes["tuya_cloud"] = bool(
                routes.get("tuya_cloud")
                or (tid and command_code)
            )
        warnings = target.setdefault("warnings", [])
        warnings[:] = [w for w in warnings if "shared Tuya account" not in w]

    existing.sort(key=lambda d: (0 if d.get("lan_ip") else 1, txt(d.get("name")).lower(), txt(d.get("physical_id"))))
    model["tuya_account"] = {
        "connected": True,
        "username": account.get("username"),
        "device_count": len(rows),
        "home_count": account.get("home_count"),
        "matching_rule": "exact deviceId only",
        "token_storage": "MoniK server sharing session; reused automatically and refreshed in the same session file",
    }
    _recount_model(model)
    return model


def public_model(model: dict) -> dict:
    copy = json.loads(json.dumps(model, ensure_ascii=False))
    for device in copy.get("devices", []): device.pop("local_key", None)
    return copy


class Remote:
    def __init__(self): self.lock=threading.RLock(); self.proc=None; self.pending={}; self.tail=[]
    def ssh(self):
        for p in [shutil.which("ssh"), str(pathlib.Path(os.environ.get("WINDIR",r"C:\Windows"))/"System32"/"OpenSSH"/"ssh.exe")]:
            if p and pathlib.Path(p).is_file(): return p
        raise FileNotFoundError("Windows OpenSSH ssh.exe was not found")
    def key(self):
        here=pathlib.Path(__file__).resolve().parent
        for p in [here/"monik_strato_ed25519",pathlib.Path.home()/"Downloads"/"monik_strato_ed25519",pathlib.Path(r"S:\MY PROJECTS\ALL PROJECTS\MY VOICE PROJEKTS AND MORE\TUYA API\MoniK DOMEIN-Site\monik_strato_ed25519")]:
            if p.is_file(): return p
        raise FileNotFoundError("monik_strato_ed25519 was not found")
    def secure(self,p):
        if os.name!="nt": return
        try:
            who=subprocess.run(["whoami","/user","/fo","csv","/nh"],capture_output=True,text=True,timeout=10); text=who.stdout.strip().strip('"'); sid=text.split('","')[-1].strip('"') if text else ""; subprocess.run(["icacls",str(p),"/inheritance:r"],capture_output=True,text=True,timeout=20)
            if sid.startswith("S-"): subprocess.run(["icacls",str(p),"/grant:r","*"+sid+":R"],capture_output=True,text=True,timeout=20)
        except Exception: pass
    def start(self):
        with self.lock:
            if self.proc and self.proc.poll() is None: return
            key=self.key(); self.secure(key); cmd=[self.ssh(),"-T","-i",str(key),"-o","BatchMode=yes","-o","IdentitiesOnly=yes","-o","StrictHostKeyChecking=accept-new","-o","ConnectTimeout=20","-o","ServerAliveInterval=15","-o","ServerAliveCountMax=20",SSH_TARGET,"/usr/bin/node"]
            self.proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding="utf-8",errors="replace",bufsize=1); self.proc.stdin.write(REMOTE_JS+"\n"); self.proc.stdin.flush(); ready=self.proc.stdout.readline().strip()
            if ready!="MONIK_READY": raise RuntimeError("STRATO worker did not start: "+ready+"\n"+self.proc.stderr.read(3000))
            threading.Thread(target=self.reader,daemon=True).start(); threading.Thread(target=self.errors,daemon=True).start()
    def reader(self):
        for line in self.proc.stdout:
            line=line.rstrip();
            if not line.startswith("MONIK_RESP "): continue
            try:
                data=json.loads(line[11:]); q=self.pending.get(str(data.get("id"))); q and q.put(data)
            except Exception: pass
    def errors(self):
        for line in self.proc.stderr: self.tail=(self.tail+[line.rstrip()])[-100:]
    def request(self,op,timeout=70,**kw):
        self.start(); rid=uuid.uuid4().hex; q=queue.Queue(maxsize=1); self.pending[rid]=q
        try:
            with self.lock: self.proc.stdin.write(json.dumps({"id":rid,"op":op,**kw},ensure_ascii=False,separators=(",",":"))+"\n"); self.proc.stdin.flush()
            data=q.get(timeout=timeout)
        except queue.Empty: raise TimeoutError("STRATO worker timeout for "+op+"\n"+"\n".join(self.tail[-20:]))
        finally: self.pending.pop(rid,None)
        if not data.get("ok"): raise RuntimeError(data.get("error") or "Remote worker error")
        return data.get("result")
    def stop(self):
        with self.lock:
            if self.proc and self.proc.poll() is None:
                try: self.proc.terminate(); self.proc.wait(timeout=3)
                except Exception:
                    try: self.proc.kill()
                    except Exception: pass
            self.proc=None

REMOTE=Remote()



def norm_mac(value):
    value=txt(value).lower().replace("-",":")
    m=re.search(r"\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b",value)
    return m.group(0) if m else None


def arp_entries():
    """Read exact IP->MAC neighbors from all built-in Windows sources."""
    if os.name != "nt":
        return {
            "success": False,
            "entries": [],
            "error": "Windows neighbor table is required",
            "strato_used": False,
            "installs": False,
        }

    rows = {}
    errors = []

    def add(ip_value, mac_value, source):
        ip = private_ip(ip_value)
        mac = norm_mac(mac_value)
        if ip and mac and mac != "00:00:00:00:00:00":
            rows[(ip, mac)] = {"ip": ip, "mac": mac, "source": source}

    try:
        run = subprocess.run(
            ["arp", "-a"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        for line in run.stdout.splitlines():
            ipm = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", line)
            macm = re.search(
                r"\b(?:[0-9a-fA-F]{2}[-:]){5}[0-9a-fA-F]{2}\b",
                line,
            )
            if ipm and macm:
                add(ipm.group(0), macm.group(0), "arp -a")
    except Exception as exc:
        errors.append("arp: " + str(exc))

    powershell = shutil.which("powershell") or shutil.which("powershell.exe")
    if powershell:
        try:
            command = (
                "Get-NetNeighbor -AddressFamily IPv4 | "
                "Select-Object IPAddress,LinkLayerAddress,State | "
                "ConvertTo-Json -Compress"
            )
            run = subprocess.run(
                [powershell, "-NoProfile", "-Command", command],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
            )
            raw = run.stdout.strip()
            if raw:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    parsed = [parsed]
                if isinstance(parsed, list):
                    for row in parsed:
                        if isinstance(row, dict):
                            add(
                                row.get("IPAddress"),
                                row.get("LinkLayerAddress"),
                                "Get-NetNeighbor",
                            )
        except Exception as exc:
            errors.append("Get-NetNeighbor: " + str(exc))

    try:
        run = subprocess.run(
            ["netsh", "interface", "ipv4", "show", "neighbors"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        for line in run.stdout.splitlines():
            ipm = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", line)
            macm = re.search(
                r"\b(?:[0-9a-fA-F]{2}[-:]){5}[0-9a-fA-F]{2}\b",
                line,
            )
            if ipm and macm:
                add(ipm.group(0), macm.group(0), "netsh neighbors")
    except Exception as exc:
        errors.append("netsh: " + str(exc))

    entries = list(rows.values())
    return {
        "success": bool(entries),
        "entries": entries,
        "entry_count": len(entries),
        "errors": errors,
        "strato_used": False,
        "installs": False,
    }


def warm_neighbor_cache(ips: list[str], hard_limit: float = 1.2) -> None:
    """Populate Windows neighbor cache in parallel; no Tuya/status request."""
    targets = list(dict.fromkeys(ip for ip in ips if private_ip(ip)))
    if os.name != "nt" or not targets:
        return

    def touch(ip):
        try:
            subprocess.run(
                ["ping", "-n", "1", "-w", "250", ip],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=0.8,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            pass

    threads = [threading.Thread(target=touch, args=(ip,), daemon=True) for ip in targets]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + hard_limit
    for thread in threads:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        thread.join(timeout=remaining)


def refresh_known_ips(model):
    ips=sorted({private_ip(d.get("lan_ip")) for d in model.get("devices",[]) if private_ip(d.get("lan_ip"))})
    hits=[]
    for ip in ips:
        try:
            run=subprocess.run(["ping","-n","1","-w","180",ip],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=2)
            if run.returncode==0:hits.append(ip)
        except Exception: pass
    return hits


def current_private_networks() -> list[ipaddress.IPv4Network]:
    """
    Return all active private IPv4 networks.

    Windows ipconfig is used first so Wi-Fi/Ethernet adapters are not missed.
    A network larger than /24 is scanned only in the current host's /24 slice,
    which keeps the scan bounded and prevents blocking.
    """
    networks = set()

    if os.name == "nt":
        try:
            run = subprocess.run(
                ["ipconfig"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            current_ip = None
            for line in run.stdout.splitlines():
                ip_match = re.search(
                    r"(?:IPv4[^:]*|IPv4 Address[^:]*|IPv4-Adresse[^:]*):\s*"
                    r"(\d{1,3}(?:\.\d{1,3}){3})",
                    line,
                    re.I,
                )
                if ip_match:
                    current_ip = ip_match.group(1)
                    continue

                mask_match = re.search(
                    r"(?:Subnet Mask|Subnetzmaske)[^:]*:\s*"
                    r"(\d{1,3}(?:\.\d{1,3}){3})",
                    line,
                    re.I,
                )
                if current_ip and mask_match:
                    try:
                        interface = ipaddress.IPv4Interface(
                            current_ip + "/" + mask_match.group(1)
                        )
                        if interface.ip.is_private and not interface.ip.is_loopback:
                            network = interface.network
                            if network.prefixlen < 24:
                                network = ipaddress.ip_network(
                                    str(interface.ip) + "/24",
                                    strict=False,
                                )
                            networks.add(network)
                    except Exception:
                        pass
                    current_ip = None
        except Exception:
            pass

    try:
        candidates = socket.gethostbyname_ex(socket.gethostname())[2]
    except Exception:
        candidates = []

    for ip_text in candidates:
        try:
            address = ipaddress.ip_address(ip_text)
            if (
                isinstance(address, ipaddress.IPv4Address)
                and address.is_private
                and not address.is_loopback
            ):
                networks.add(
                    ipaddress.ip_network(f"{ip_text}/24", strict=False)
                )
        except Exception:
            pass

    return sorted(networks, key=str)


def configured_scan_networks() -> list[ipaddress.IPv4Network]:
    """
    Scan MONIK_SCAN_CIDR if provided, otherwise scan all active private /24s.
    This prevents the local scanner from being locked to one hard-coded subnet.
    """
    raw = os.environ.get("MONIK_SCAN_CIDR", "").strip()
    networks: list[ipaddress.IPv4Network] = []
    if raw:
        for item in re.split(r"[,;\s]+", raw):
            if not item:
                continue
            try:
                network = ipaddress.ip_network(item, strict=False)
                if isinstance(network, ipaddress.IPv4Network) and network.is_private:
                    if network.prefixlen < 24:
                        network = ipaddress.ip_network(str(next(network.hosts())) + "/24", strict=False)
                    networks.append(network)
            except Exception:
                pass
    return sorted(set(networks or current_private_networks()), key=str)


def normalize_tuya_scan_result(result: Any) -> list[dict]:
    """
    Keep every Tuya UDP identity row with a private IP and at least one
    identity characteristic. Missing deviceId must not discard UUID,
    productKey, MAC or relation IDs.
    """
    rows = []

    if isinstance(result, dict):
        iterable = result.items()
    elif isinstance(result, list):
        iterable = enumerate(result)
    else:
        iterable = []

    for key, value in iterable:
        if not isinstance(value, dict):
            continue

        ip_text = private_ip(first(
            value.get("ip"),
            key if private_ip(key) else None,
            value.get("address"),
            value.get("host"),
        ))
        if not ip_text:
            continue

        row = {
            "device_id": txt(first(
                value.get("devId"),
                value.get("deviceId"),
                value.get("device_id"),
                value.get("id"),
                value.get("gwId"),
                value.get("gw_id"),
            )) or None,
            "uuid": txt(first(
                value.get("uuid"),
                value.get("uuidId"),
                value.get("uuid_id"),
            )) or None,
            "node_id": txt(first(
                value.get("nodeId"),
                value.get("node_id"),
            )) or None,
            "gateway_id": txt(first(
                value.get("gatewayId"),
                value.get("gateway_id"),
                value.get("gw_id"),
                value.get("gwId"),
            )) or None,
            "parent_id": txt(first(
                value.get("parentId"),
                value.get("parent_id"),
            )) or None,
            "ip": ip_text,
            "version": first(
                value.get("version"),
                value.get("ver"),
                value.get("protocolVersion"),
            ),
            "mac": norm_mac(first(
                value.get("mac"),
                value.get("macAddress"),
                value.get("mac_address"),
            )),
            "product_key": txt(first(
                value.get("productKey"),
                value.get("product_id"),
                value.get("productId"),
                value.get("product_key"),
            )) or None,
            "category": txt(value.get("category")) or None,
            "name": txt(first(
                value.get("name"),
                value.get("product_name"),
                value.get("productName"),
            )) or None,
            "raw": value,
        }

        if any((
            row["device_id"],
            row["uuid"],
            row["mac"],
            row["product_key"],
            row["node_id"],
            row["gateway_id"],
            row["parent_id"],
        )):
            rows.append(row)

    unique = {}
    for row in rows:
        key = (
            row.get("ip"),
            row.get("device_id"),
            row.get("uuid"),
            row.get("mac"),
            row.get("product_key"),
            row.get("node_id"),
            row.get("gateway_id"),
            row.get("parent_id"),
        )
        unique[key] = row

    return list(unique.values())


def udp_tuya_discovery_scan(scan_seconds: float = 9.0) -> dict:
    """
    Tuya UDP identity discovery only. No status and no DP command.

    The v3.5 discovery request is repeated, so devices that miss the first
    broadcast can answer on a later request.
    """
    summary = {
        "available": bool(importlib.util.find_spec("tinytuya")),
        "success": False,
        "devices": [],
        "device_count": 0,
        "ports": [6666, 6667, 6668, 7000],
        "commands_sent": False,
        "status_used": False,
        "installs": False,
    }

    if not summary["available"]:
        summary["error"] = "tinytuya_not_available_nothing_installed"
        return summary

    child_code = r"""
import json
import select
import socket
import time
import tinytuya

ports = (6666, 6667, 6668, 7000)
sockets = []
rows = []
errors = []

for port in ports:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", port))
        sock.setblocking(False)
        sockets.append(sock)
    except Exception as exc:
        errors.append("bind %s: %s" % (port, exc))

try:
    scanner = getattr(tinytuya, "scanner", None)
    if scanner is None:
        import tinytuya.scanner as scanner
    sender = getattr(scanner, "send_discovery_request", None)
except Exception as exc:
    sender = None
    errors.append("scanner load: %s" % exc)

deadline = time.monotonic() + SCAN_SECONDS
next_request = 0.0

while time.monotonic() < deadline:
    now = time.monotonic()

    if callable(sender) and now >= next_request:
        try:
            sender()
        except Exception as exc:
            errors.append("discovery request: %s" % exc)
        next_request = now + 0.70

    if not sockets:
        time.sleep(0.05)
        continue

    readable, _, _ = select.select(
        sockets,
        [],
        [],
        min(0.20, max(0.0, deadline - time.monotonic())),
    )

    for sock in readable:
        try:
            packet, address = sock.recvfrom(65535)
        except Exception:
            continue

        decoded = None
        try:
            decoded = tinytuya.decrypt_udp(packet)
        except Exception:
            try:
                decoded = packet.decode("utf-8", errors="ignore")
            except Exception:
                decoded = None

        if not decoded:
            continue

        try:
            value = json.loads(decoded)
        except Exception:
            continue

        if not isinstance(value, dict):
            continue

        value.setdefault("ip", address[0])
        value["_source_port"] = sock.getsockname()[1]
        rows.append(value)

for sock in sockets:
    try:
        sock.close()
    except Exception:
        pass

print(
    "MONIK_UDP_RESULT "
    + json.dumps(
        {"rows": rows, "errors": errors},
        ensure_ascii=False,
        separators=(",", ":"),
    )
)
""".replace("SCAN_SECONDS", repr(float(scan_seconds)))

    try:
        run = subprocess.run(
            [sys.executable, "-c", child_code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=scan_seconds + 3.0,
            creationflags=(
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                if os.name == "nt"
                else 0
            ),
        )

        payload = None
        for line in reversed(run.stdout.splitlines()):
            if line.startswith("MONIK_UDP_RESULT "):
                payload = json.loads(
                    line[len("MONIK_UDP_RESULT "):]
                )
                break

        if payload is None:
            raise RuntimeError(
                "UDP discovery returned no result"
                + (
                    ": " + run.stderr.strip()
                    if run.stderr.strip()
                    else ""
                )
            )

        devices = normalize_tuya_scan_result(
            payload.get("rows", [])
        )
        summary.update({
            "success": True,
            "devices": devices,
            "device_count": len(devices),
            "listener_errors": payload.get("errors", []),
        })
        return summary

    except subprocess.TimeoutExpired:
        summary["error"] = "udp_discovery_hard_timeout"
        return summary
    except Exception as exc:
        summary["error"] = str(exc)
        return summary


def tcp_tuya_port_scan(
    networks: list[ipaddress.IPv4Network],
    ports: tuple[int, ...] = (6668, 6667),
) -> dict:
    """
    Fast bounded TCP scan of Tuya ports 6668 and 6667.

    Connecting to each address also refreshes the Windows ARP table.
    No Tuya control command or DP command is sent.
    """
    hosts = []
    for network in networks:
        hosts.extend(str(host) for host in network.hosts())

    hosts = sorted(set(hosts))
    result = {}
    lock = threading.Lock()
    queue_hosts = queue.Queue()

    for host in hosts:
        queue_hosts.put(host)

    worker_count = min(96, max(1, len(hosts)))

    def worker() -> None:
        while True:
            try:
                host = queue_hosts.get_nowait()
            except queue.Empty:
                return

            open_ports = []
            for port in ports:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    sock.settimeout(0.22)
                    if sock.connect_ex((host, port)) == 0:
                        open_ports.append(port)
                except Exception:
                    pass
                finally:
                    try:
                        sock.close()
                    except Exception:
                        pass

            if open_ports:
                with lock:
                    result[host] = open_ports

    threads = [
        threading.Thread(target=worker, daemon=True)
        for _ in range(worker_count)
    ]
    for thread in threads:
        thread.start()

    deadline = time.monotonic() + 4.5
    for thread in threads:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        thread.join(timeout=remaining)

    rows = [
        {"ip": ip_text, "ports": result[ip_text]}
        for ip_text in sorted(
            result,
            key=lambda value: tuple(int(part) for part in value.split(".")),
        )
    ]

    return {
        "success": True,
        "networks": [str(network) for network in networks],
        "ports": list(ports),
        "candidates": rows,
        "candidate_count": len(rows),
        "hosts_considered": len(hosts),
        "hard_limit_seconds": 4.5,
        "commands_sent": False,
        "installs": False,
    }



def nmap_6668_scan(networks: list[ipaddress.IPv4Network] | None = None) -> dict:
    """
    Execute nmap for every configured/current private /24:

        nmap -p 6668 -Pn --open --traceroute <network>

    Parse IP, hostname, TCP 6668 and MAC Address from Nmap. If Nmap omits a
    MAC line, read the already-populated Windows ARP table once and attach
    the exact IP -> MAC pair. No Tuya command is sent.
    """
    networks = networks or configured_scan_networks()
    outputs = []
    commands = []
    returncodes = []

    if not networks:
        return {
            "success": False,
            "error": "no_private_scan_network_detected",
            "commands": [],
            "candidates": [],
            "candidate_count": 0,
            "commands_sent": False,
        }

    for network in networks:
        command = [
            "nmap",
            "-p",
            "6668",
            "-Pn",
            "--open",
            "--traceroute",
            str(network),
        ]
        commands.append(" ".join(command))
        print("[LAN] Running exact command: " + " ".join(command), flush=True)

        try:
            run = subprocess.run(
                command,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=float(os.environ.get("MONIK_NMAP_TIMEOUT", "8")),
                creationflags=(
                    getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    if os.name == "nt"
                    else 0
                ),
            )
            returncodes.append(run.returncode)
            outputs.append((run.stdout or "") + (("\n" + run.stderr) if run.stderr else ""))
        except FileNotFoundError:
            return {
                "success": False,
                "error": "nmap_not_found",
                "commands": commands,
                "candidates": [],
                "candidate_count": 0,
                "commands_sent": False,
            }
        except subprocess.TimeoutExpired as exc:
            outputs.append((exc.stdout or "") + "\n" + (exc.stderr or ""))
            returncodes.append(124)

    output = "\n".join(outputs)

    candidates = []
    current_ip = None
    current_host = None
    current_mac = None
    port_open = False

    report_re = re.compile(
        r"^Nmap scan report for (?:(.*?) \()?(\d{1,3}(?:\.\d{1,3}){3})\)?$"
    )
    mac_re = re.compile(
        r"^MAC Address:\s*((?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2})\b"
    )

    def finish_host() -> None:
        nonlocal current_ip, current_host, current_mac, port_open
        if current_ip and port_open:
            candidates.append(
                {
                    "ip": current_ip,
                    "host": current_host,
                    "mac": norm_mac(current_mac),
                    "ports": [6668],
                    "source": "exact_nmap_6668",
                }
            )
        current_ip = None
        current_host = None
        current_mac = None
        port_open = False

    for raw_line in output.splitlines():
        line = raw_line.strip()

        report_match = report_re.match(line)
        if report_match:
            finish_host()
            current_host = (
                (report_match.group(1) or "").strip() or None
            )
            current_ip = private_ip(report_match.group(2))
            continue

        if current_ip and re.match(
            r"^6668/tcp\s+open\b",
            line,
            flags=re.IGNORECASE,
        ):
            port_open = True
            continue

        mac_match = mac_re.match(line)
        if current_ip and mac_match:
            current_mac = norm_mac(mac_match.group(1))

    finish_host()

    unique = []
    seen = set()
    for row in candidates:
        if row["ip"] in seen:
            continue
        seen.add(row["ip"])
        unique.append(row)

    # Populate and read the exact Windows neighbor table for all open hosts.
    warm_neighbor_cache([row["ip"] for row in unique])
    arp_by_ip = {}
    try:
        arp = arp_entries()
        arp_by_ip = {
            private_ip(row.get("ip")): norm_mac(row.get("mac"))
            for row in arp.get("entries", [])
            if private_ip(row.get("ip")) and norm_mac(row.get("mac"))
        }
    except Exception:
        arp_by_ip = {}

    for row in unique:
        if not row.get("mac"):
            row["mac"] = arp_by_ip.get(row["ip"])

    print(
        "[LAN] Nmap completed: "
        f"open TCP 6668 devices={len(unique)}, "
        f"MAC addresses={sum(1 for row in unique if row.get('mac'))}.",
        flush=True,
    )

    return {
        "success": any(code == 0 for code in returncodes) or bool(unique),
        "returncodes": returncodes,
        "commands": commands,
        "raw_output": output,
        "networks": [str(network) for network in networks],
        "candidates": unique,
        "candidate_count": len(unique),
        "mac_count": sum(1 for row in unique if row.get("mac")),
        "commands_sent": False,
        "installs": False,
    }


def tinytuya_lan_scan() -> dict:
    """
    LAN discovery order:

      1. exact requested nmap command for every open TCP 6668 host;
      2. Tuya UDP 6666/6667/6668/7000 only for exact deviceId/IP metadata;
      3. the device model is then built from the selected JSON and matched
         against the nmap addresses.
    """
    networks = configured_scan_networks()
    # Fast scanner path: TCP 6668 first. Nmap is optional/enrichment only,
    # because Windows nmap can make the UI look frozen. Set MONIK_USE_NMAP=1
    # when exact nmap output is required.
    fallback = tcp_tuya_port_scan(networks, (6668,))
    nmap_result = {
        "success": bool(fallback.get("candidate_count")),
        "commands": ["fast tcp scan 6668"],
        "candidates": [
            {"ip": row["ip"], "mac": None, "ports": row.get("ports", [6668]), "source": "fast_tcp_6668"}
            for row in fallback.get("candidates", [])
        ],
        "candidate_count": fallback.get("candidate_count", 0),
        "fallback_tcp_scan": fallback,
        "commands_sent": False,
        "installs": False,
    }
    if os.environ.get("MONIK_USE_NMAP") == "1":
        nmap_try = nmap_6668_scan(networks)
        if nmap_try.get("success"):
            nmap_result = nmap_try

    print(
        "[LAN] Reading Tuya UDP 6666/6667/6668/7000 "
        "for exact deviceId mapping...",
        flush=True,
    )
    udp_result = udp_tuya_discovery_scan(7.0)

    devices = udp_result.get("devices", [])
    candidates = nmap_result.get("candidates", [])

    summary = {
        "available": udp_result.get("available"),
        "success": bool(
            nmap_result.get("success")
            or udp_result.get("success")
        ),
        "devices": devices,
        "device_count": len(devices),
        "udp": udp_result,
        "nmap": nmap_result,
        "port_candidates": candidates,
        "port_candidate_count": len(candidates),
        "commands_sent": False,
        "installs": False,
        "scan_order": [
            "exact nmap TCP 6668",
            "Tuya UDP exact deviceId",
            "selected JSON device construction",
        ],
    }

    if not summary["success"]:
        summary["error"] = " | ".join(
            value
            for value in (
                str(nmap_result.get("error") or ""),
                str(udp_result.get("error") or ""),
            )
            if value
        )

    print(
        "[LAN] Discovery completed: "
        f"nmap 6668={summary['port_candidate_count']}, "
        f"exact UDP deviceId={summary['device_count']}.",
        flush=True,
    )
    return summary


def refresh_arp_cache_for_discovered_ips(ips: list[str]) -> int:
    """
    Refresh ARP with one global deadline.

    The old code joined every ping thread separately for up to 3 seconds,
    which could make the request appear frozen. This version never waits
    longer than 1.5 seconds in total.
    """
    hits = 0
    hits_lock = threading.Lock()
    addresses = sorted(
        {
            ip_text
            for ip_text in ips
            if private_ip(ip_text)
        }
    )

    def ping_one(ip_text: str) -> None:
        nonlocal hits
        try:
            run = subprocess.run(
                ["ping", "-n", "1", "-w", "180", ip_text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=0.8,
                creationflags=(
                    getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    if os.name == "nt"
                    else 0
                ),
            )
            if run.returncode == 0:
                with hits_lock:
                    hits += 1
        except Exception:
            pass

    threads = [
        threading.Thread(
            target=ping_one,
            args=(ip_text,),
            daemon=True,
        )
        for ip_text in addresses
    ]

    for thread in threads:
        thread.start()

    deadline = time.monotonic() + 1.5
    for thread in threads:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        thread.join(timeout=remaining)

    return hits



def _identity_indexes(devices: list[dict]) -> dict:
    indexes = {
        "device_id": {},
        "uuid": {},
        "mac": {},
        "node_id": {},
        "gateway_id": {},
        "parent_id": {},
        "product_key": {},
        "product_version": {},
    }

    def add(kind, value, device):
        key = txt(value).lower()
        if key:
            indexes[kind].setdefault(key, []).append(device)

    for device in devices:
        add("device_id", device.get("tuya_id"), device)
        add("uuid", device.get("uuid"), device)
        add("mac", norm_mac(device.get("mac")), device)
        add("node_id", device.get("node_id"), device)
        add("gateway_id", device.get("gateway_id"), device)
        add("parent_id", device.get("parent_id"), device)
        add("product_key", device.get("product_id"), device)

        product = txt(device.get("product_id")).lower()
        version = txt(device.get("protocol_version")).lower()
        if product and version:
            add(
                "product_version",
                product + "|" + version,
                device,
            )

    return indexes


def _unique_index_match(index: dict, value) -> dict | None:
    rows = index.get(txt(value).lower(), [])
    return rows[0] if len(rows) == 1 else None


def _apply_lan_matches(model, nmap_rows, matches, source):
    nmap_by_ip = {
        private_ip(row.get("ip")): row
        for row in nmap_rows
        if private_ip(row.get("ip"))
    }
    claimed_ips = {
        private_ip(match.get("ip"))
        for match in matches.values()
        if private_ip(match.get("ip"))
    }

    for device in model.get("devices", []):
        device_id = txt(device.get("tuya_id"))
        match = matches.get(device_id)
        current = bool(match)

        if match:
            device["lan_ip"] = match["ip"]
            if match.get("version"):
                device["protocol_version"] = str(
                    match["version"]
                )
            if (
                match.get("nmap_mac")
                and not norm_mac(device.get("mac"))
            ):
                device["mac"] = match["nmap_mac"]

        device["local_candidate"] = current
        device["current_lan_match"] = current
        device["local_match_method"] = (
            match.get("method") if match else None
        )
        device["lan_discovery"] = {
            "matched": current,
            "method": (
                match.get("method") if match else None
            ),
            "matching_source": source,
            "device_id": device_id,
            "uuid": txt(device.get("uuid")) or None,
            "ip": (
                match.get("ip")
                if match
                else private_ip(device.get("lan_ip"))
            ),
            "nmap_mac": (
                match.get("nmap_mac") if match else None
            ),
            "status_used": bool(match.get("status_used")) if match else False,
            "status_dp_overlap": match.get("status_dp_overlap", []) if match else [],
            "status_match_confidence": match.get("status_match_confidence") if match else None,
            "device_mac": norm_mac(device.get("mac")),
            "ports": [6668] if current else [],
        }

        for control in device.get("controls", []):
            routes = control.setdefault("routes", {})

            if control.get("virtual"):
                local_command = bool(
                    control.get("virtual_actions")
                    and any(
                        action.get("code")
                        and action.get("dp_id") is not None
                        for action in control.get(
                            "virtual_actions",
                            [],
                        )
                    )
                )
                cloud_command = bool(
                    control.get("virtual_actions")
                    and any(
                        txt(action.get("code"))
                        for action in control.get(
                            "virtual_actions",
                            [],
                        )
                    )
                )
            else:
                local_command = bool(
                    control.get("command_code")
                    and control.get("dp_id") is not None
                )
                cloud_command = bool(
                    txt(
                        control.get("command_code")
                        or control.get("code")
                    )
                )

            routes["local"] = bool(
                device.get("local_key")
                and device_id
                and local_command
            )
            routes["local_current"] = bool(
                routes["local"] and current
            )
            routes["tuya_cloud"] = bool(
                routes.get("tuya_cloud")
                or (device_id and cloud_command)
            )

        device["has_local_control_data"] = bool(
            device.get("local_key")
            and device_id
            and any(
                control.get("routes", {}).get("local")
                for control in device.get("controls", [])
            )
        )

        coverage = device.setdefault("coverage", {})
        coverage["local_data_ready"] = sum(
            1
            for control in device.get("controls", [])
            if control.get("routes", {}).get("local")
        )
        coverage["local_current_lan_ready"] = sum(
            1
            for control in device.get("controls", [])
            if control.get("routes", {}).get(
                "local_current"
            )
        )
        coverage["local_route_ready"] = coverage[
            "local_current_lan_ready"
        ]
        coverage["tuya_cloud_route_ready"] = sum(
            1
            for control in device.get("controls", [])
            if control.get("routes", {}).get(
                "tuya_cloud"
            )
        )

    model["devices"].sort(
        key=lambda device: (
            0 if device.get("current_lan_match") else 1,
            0 if device.get("has_local_control_data") else 1,
            txt(device.get("name")).lower(),
            txt(device.get("physical_id")),
        )
    )

    unresolved = [
        {
            "ip": ip,
            "mac": norm_mac(row.get("mac")),
            "host": row.get("host"),
            "ports": row.get("ports", [6668]),
        }
        for ip, row in nmap_by_ip.items()
        if ip not in claimed_ips
    ]

    model["lan_scan"] = {
        **model.get("lan_scan", {}),
        "success": bool(nmap_rows),
        "command": model.get("lan_scan", {}).get("command") or source or "fast tcp scan 6668",
        "nmap_candidates": nmap_rows,
        "open_6668_count": len(nmap_by_ip),
        "current_lan_tuya_hosts": len(nmap_by_ip),
        "nmap_mac_count": sum(
            1
            for row in nmap_rows
            if norm_mac(row.get("mac"))
        ),
        "matched_account_devices": len(matches),
        "unresolved_local_host_count": len(unresolved),
        "unresolved_local_hosts": unresolved,
        "unmatched_open_6668_ips": [
            row["ip"] for row in unresolved
        ],
        "status_used_for_matching": bool(any(match.get("status_used") for match in matches.values())),
        "commands_sent": False,
        "installs": False,
    }



def _device_dp_id_set(device: dict) -> set[str]:
    ids: set[str] = set()
    for control in device.get("controls", []) or []:
        dp_id = control.get("dp_id")
        if dp_id is not None and str(dp_id).isdigit():
            ids.add(str(dp_id))
    for key in (device.get("status") or {}).keys():
        if str(key).isdigit():
            ids.add(str(key))
    for key in (device.get("dp_map") or {}).values():
        if str(key).isdigit():
            ids.add(str(key))
    return ids


def _status_dp_id_set(status_payload: Any) -> set[str]:
    candidates = []
    if isinstance(status_payload, dict):
        for key in ("dps", "status", "result"):
            value = status_payload.get(key)
            if isinstance(value, dict):
                candidates.append(value)
        candidates.append(status_payload)
    ids: set[str] = set()
    for mapping in candidates:
        for key in mapping.keys():
            if str(key).isdigit():
                ids.add(str(key))
    return ids


def _status_probe_one(ip: str, device: dict, timeout: float) -> dict:
    """
    Read-only local status probe. localKey is used only here, never as identity by itself.
    No set_value, no ON/OFF, no DP write.
    """
    if not importlib.util.find_spec("tinytuya"):
        return {"success": False, "error": "tinytuya_not_available"}

    device_id = txt(device.get("tuya_id"))
    key = txt(device.get("local_key"))
    version = txt(device.get("protocol_version") or "3.3")
    expected_dp_ids = _device_dp_id_set(device)
    if not device_id or not key or not expected_dp_ids:
        return {"success": False, "error": "missing_device_id_key_or_dp_schema"}

    box: dict[str, Any] = {}

    def run():
        try:
            import tinytuya  # type: ignore
            obj = tinytuya.Device(device_id, ip, key)
            try:
                obj.set_version(float(version))
            except Exception:
                obj.set_version(3.3)
            if hasattr(obj, "set_socketTimeout"):
                try:
                    obj.set_socketTimeout(timeout)
                except Exception:
                    pass
            status_payload = obj.status()
            returned_dp_ids = _status_dp_id_set(status_payload)
            overlap = sorted(expected_dp_ids & returned_dp_ids, key=lambda value: int(value) if value.isdigit() else value)
            box["result"] = {
                "success": bool(overlap) or bool(returned_dp_ids),
                "match_confidence": "dp_overlap" if overlap else ("status_positive_no_overlap" if returned_dp_ids else "no_status_dps"),
                "status_payload": status_payload,
                "returned_dp_ids": sorted(returned_dp_ids),
                "expected_dp_ids": sorted(expected_dp_ids),
                "dp_overlap": overlap,
                "protocol_version": version,
            }
        except Exception as exc:
            box["result"] = {"success": False, "error": str(exc), "protocol_version": version}

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout + 0.4)
    if thread.is_alive():
        return {"success": False, "error": "status_probe_timeout", "protocol_version": version}
    return box.get("result", {"success": False, "error": "status_probe_no_result", "protocol_version": version})


def _external_ip_probe_groups(devices: list[dict]) -> list[tuple[str, list[dict]]]:
    grouped: dict[str, list[dict]] = {}
    for device in devices:
        external_ip = public_ip(device.get("external_ip"))
        if external_ip:
            grouped.setdefault(external_ip, []).append(device)
    groups = [(ip, rows) for ip, rows in grouped.items() if len(rows) >= 3]
    groups.sort(key=lambda item: len(item[1]), reverse=True)
    return groups


def _status_match_unresolved_lan(model, nmap_rows, matches, claimed_ids, claimed_ips) -> dict:
    """
    Resolve only still-unmatched LAN IPs through read-only status().
    Search is shortened by external-IP groups first: when the JSON has >=3 devices
    sharing one external IP, that group is probed first. Only after that group is
    exhausted do we try the remaining JSON devices.
    """
    if not importlib.util.find_spec("tinytuya"):
        return {
            "added": 0,
            "attempts": 0,
            "enabled": False,
            "reason": "tinytuya_not_available",
            "external_ip_groups": [],
        }

    timeout = max(0.25, float(os.environ.get("MONIK_STATUS_MATCH_TIMEOUT", "0.65")))
    max_probes = max(1, int(os.environ.get("MONIK_STATUS_MATCH_MAX_PROBES", "160")))
    worker_count = max(1, int(os.environ.get("MONIK_STATUS_MATCH_WORKERS", "24")))
    devices = [
        device for device in model.get("devices", [])
        if txt(device.get("tuya_id"))
        and txt(device.get("local_key"))
        and _device_dp_id_set(device)
        and txt(device.get("tuya_id")) not in claimed_ids
    ]
    open_ips = [
        private_ip(row.get("ip")) for row in nmap_rows
        if private_ip(row.get("ip")) and private_ip(row.get("ip")) not in claimed_ips
    ]
    open_ips = [ip for ip in open_ips if ip]
    external_groups = _external_ip_probe_groups(devices)
    probe_log = []
    probe_queue: queue.Queue[tuple[str, str, dict]] = queue.Queue()
    state_lock = threading.Lock()
    attempts = 0
    added = 0

    def candidate_batches():
        grouped_ids = set()
        for external_ip, rows in external_groups:
            batch = [device for device in rows if txt(device.get("tuya_id")) not in claimed_ids]
            grouped_ids.update(txt(device.get("tuya_id")) for device in batch)
            if batch:
                yield f"external_ip:{external_ip}", batch
        rest = [device for device in devices if txt(device.get("tuya_id")) not in claimed_ids and txt(device.get("tuya_id")) not in grouped_ids]
        if rest:
            yield "remaining_json_devices_after_external_ip_groups", rest

    for ip in open_ips:
        for batch_name, batch in candidate_batches():
            for device in batch:
                if probe_queue.qsize() >= max_probes:
                    break
                probe_queue.put((ip, batch_name, device))
            if probe_queue.qsize() >= max_probes:
                break
        if probe_queue.qsize() >= max_probes:
            break

    def worker() -> None:
        nonlocal attempts, added
        while True:
            try:
                ip, batch_name, device = probe_queue.get_nowait()
            except queue.Empty:
                return
            device_id = txt(device.get("tuya_id"))
            with state_lock:
                if not device_id or device_id in claimed_ids or ip in claimed_ips:
                    continue
                attempts += 1
            result = _status_probe_one(ip, device, timeout)
            row = {
                "ip": ip,
                "device_id": device_id,
                "device_name": device.get("name"),
                "batch": batch_name,
                "success": bool(result.get("success")),
                "dp_overlap": result.get("dp_overlap", []),
                "error": result.get("error"),
            }
            with state_lock:
                probe_log.append(row)
                if result.get("success") and device_id not in claimed_ids and ip not in claimed_ips:
                    claimed_ids.add(device_id)
                    claimed_ips.add(ip)
                    matches[device_id] = {
                        "ip": ip,
                        "method": "local_status_deviceId_localKey_dp_overlap",
                        "version": result.get("protocol_version") or device.get("protocol_version"),
                        "nmap_mac": norm_mac(next((row.get("mac") for row in nmap_rows if private_ip(row.get("ip")) == ip), None)),
                        "status_dp_overlap": result.get("dp_overlap", []),
                        "status_match_confidence": result.get("match_confidence"),
                        "status_used": True,
                    }
                    added += 1

    threads = [
        threading.Thread(target=worker, daemon=True)
        for _ in range(min(worker_count, max(1, probe_queue.qsize())))
    ]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + float(os.environ.get("MONIK_STATUS_MATCH_DEADLINE", "8.0"))
    for thread in threads:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        thread.join(timeout=remaining)

    return {
        "added": added,
        "attempts": attempts,
        "enabled": True,
        "timeout_seconds": timeout,
        "max_probes": max_probes,
        "workers": worker_count,
        "deadline_seconds": float(os.environ.get("MONIK_STATUS_MATCH_DEADLINE", "8.0")),
        "external_ip_groups": [
            {"external_ip": ip, "device_count": len(rows)} for ip, rows in external_groups
        ],
        "probe_log": probe_log[:80],
    }


def apply_arp(model):
    """
    LAN identity matching. Only read-only status() may use localKey, and only
    after UDP/nmap/saved-IP matching has not resolved an open 6668 IP.

    Sources:
      1. exact UDP deviceId
      2. exact UDP UUID
      3. exact UDP MAC
      4. exact node/gateway/parent ID
      5. unique productKey + protocol version
      6. unique productKey
      7. exact saved private IP
    """
    udp_box = {}

    def run_udp():
        udp_box["result"] = udp_tuya_discovery_scan(9.0)

    udp_thread = threading.Thread(
        target=run_udp,
        daemon=True,
    )
    udp_thread.start()

    networks = configured_scan_networks()
    # Fast scanner path: TCP 6668 first. Nmap is optional/enrichment only,
    # because Windows nmap can make the UI look frozen. Set MONIK_USE_NMAP=1
    # when exact nmap output is required.
    fallback = tcp_tuya_port_scan(networks, (6668,))
    nmap_result = {
        "success": bool(fallback.get("candidate_count")),
        "commands": ["fast tcp scan 6668"],
        "candidates": [
            {"ip": row["ip"], "mac": None, "ports": row.get("ports", [6668]), "source": "fast_tcp_6668"}
            for row in fallback.get("candidates", [])
        ],
        "candidate_count": fallback.get("candidate_count", 0),
        "fallback_tcp_scan": fallback,
        "commands_sent": False,
        "installs": False,
    }
    if os.environ.get("MONIK_USE_NMAP") == "1":
        nmap_try = nmap_6668_scan(networks)
        if nmap_try.get("success"):
            nmap_result = nmap_try
    udp_thread.join(timeout=9.3)

    udp = udp_box.get("result") or {
        "devices": [],
        "error": "UDP discovery did not finish",
    }

    nmap_rows = [
        row
        for row in nmap_result.get("candidates", [])
        if private_ip(row.get("ip"))
    ]
    nmap_by_ip = {
        private_ip(row.get("ip")): row
        for row in nmap_rows
    }
    model.setdefault("lan_scan", {})["command"] = " | ".join(nmap_result.get("commands", [])) or "fast tcp scan 6668"

    devices = model.get("devices", [])
    if not devices and nmap_rows:
        model["source_name"] = model.get("source_name") or "LAN scanner only"
        model["physical_device_count"] = len(nmap_rows)
        model["logical_endpoint_count"] = 0
        model["control_count"] = 0
        model["global_warnings"] = [
            "No JSON model is loaded; showing LAN-only Tuya 6668 candidates.",
        ]
        model["devices"] = [
            {
                "physical_id": "lan:" + row["ip"],
                "tuya_id": None,
                "name": "LAN Tuya candidate " + row["ip"],
                "category": "lan-scan",
                "product_id": None,
                "product_name": None,
                "manufacturer": None,
                "model": None,
                "online": None,
                "mac": norm_mac(row.get("mac")),
                "lan_ip": row["ip"],
                "external_ip": None,
                "has_local_key": False,
                "local_key": None,
                "protocol_version": "3.3",
                "logical_endpoints": [],
                "schema_channel_count": 0,
                "schema_channel_count_sources": [],
                "status": {},
                "controls": [],
                "coverage": {
                    "records_found": 0,
                    "tuya_schema_codes": 0,
                    "dp_id_mappings": 0,
                    "status_codes": 0,
                    "yandex_logical_endpoints": 0,
                    "controls_built": 0,
                    "local_route_ready": 0,
                    "tuya_cloud_route_ready": 0,
                    "yandex_route_ready": 0,
                },
                "warnings": [
                    "LAN scanner found open 6668, but no JSON identity/localKey is loaded for this IP.",
                ],
            }
            for row in nmap_rows
        ]
        devices = model["devices"]

    external_groups_for_current_lan = _external_ip_probe_groups(devices)
    active_external_ips = {external_ip for external_ip, _rows in external_groups_for_current_lan}
    for device in devices:
        device_external_ip = public_ip(device.get("external_ip"))
        device["same_external_ip_group"] = bool(device_external_ip and device_external_ip in active_external_ips)
        if device["same_external_ip_group"] and not device.get("current_lan_match"):
            device.setdefault("warnings", []).append(
                "Same external IP group as the current LAN scan; not labeled as other network, but exact local IP is still unresolved."
            )

    indexes = _identity_indexes(devices)

    claimed_ids = set()
    claimed_ips = set()
    matches = {}
    counts = {
        "device_id": 0,
        "uuid": 0,
        "mac": 0,
        "relation_id": 0,
        "product_version": 0,
        "product_unique": 0,
        "saved_ip": 0,
        "status_dp": 0,
    }

    def claim(device, ip, method, version=None, mac=None):
        device_id = txt(device.get("tuya_id"))
        ip = private_ip(ip)

        if (
            not device_id
            or not ip
            or ip not in nmap_by_ip
            or device_id in claimed_ids
            or ip in claimed_ips
        ):
            return False

        claimed_ids.add(device_id)
        claimed_ips.add(ip)
        matches[device_id] = {
            "ip": ip,
            "method": method,
            "version": version,
            "nmap_mac": norm_mac(
                mac or nmap_by_ip[ip].get("mac")
            ),
        }
        return True

    udp_rows = udp.get("devices", [])

    for row in udp_rows:
        ip = private_ip(row.get("ip"))
        if not ip or ip not in nmap_by_ip:
            continue

        candidates = [
            (
                "device_id",
                _unique_index_match(
                    indexes["device_id"],
                    row.get("device_id"),
                ),
                "exact_udp_deviceId",
            ),
            (
                "uuid",
                _unique_index_match(
                    indexes["uuid"],
                    row.get("uuid"),
                ),
                "exact_udp_UUID",
            ),
            (
                "mac",
                _unique_index_match(
                    indexes["mac"],
                    norm_mac(row.get("mac")),
                ),
                "exact_udp_MAC",
            ),
        ]

        relation_device = None
        relation_name = None
        for kind, value in (
            ("node_id", row.get("node_id")),
            ("gateway_id", row.get("gateway_id")),
            ("parent_id", row.get("parent_id")),
        ):
            device = _unique_index_match(
                indexes[kind],
                value,
            )
            if device:
                relation_device = device
                relation_name = kind
                break

        candidates.append((
            "relation_id",
            relation_device,
            (
                "exact_udp_" + relation_name
                if relation_name
                else "exact_udp_relation_id"
            ),
        ))

        product = txt(row.get("product_key")).lower()
        version = txt(row.get("version")).lower()

        product_version_device = None
        if product and version:
            product_version_device = _unique_index_match(
                indexes["product_version"],
                product + "|" + version,
            )

        candidates.append((
            "product_version",
            product_version_device,
            "unique_udp_productKey_protocolVersion",
        ))
        candidates.append((
            "product_unique",
            _unique_index_match(
                indexes["product_key"],
                product,
            ),
            "unique_udp_productKey",
        ))

        for count_name, device, method in candidates:
            if device and claim(
                device,
                ip,
                method,
                row.get("version"),
                row.get("mac"),
            ):
                counts[count_name] += 1
                break

    for device in devices:
        known_ip = private_ip(device.get("lan_ip"))
        if known_ip in nmap_by_ip and claim(
            device,
            known_ip,
            "exact_saved_private_ip",
            device.get("protocol_version"),
            nmap_by_ip[known_ip].get("mac"),
        ):
            counts["saved_ip"] += 1

    status_match = _status_match_unresolved_lan(
        model,
        nmap_rows,
        matches,
        claimed_ids,
        claimed_ips,
    )
    counts["status_dp"] = status_match.get("added", 0)

    _apply_lan_matches(
        model,
        nmap_rows,
        matches,
        "udp_nmap_plus_status_dp",
    )

    model["lan_scan"].update({
        "udp_identity_row_count": len(udp_rows),
        "exact_udp_device_id_matches": counts["device_id"],
        "exact_udp_uuid_matches": counts["uuid"],
        "exact_udp_mac_matches": counts["mac"],
        "exact_udp_relation_id_matches": counts[
            "relation_id"
        ],
        "unique_product_version_matches": counts[
            "product_version"
        ],
        "unique_product_matches": counts[
            "product_unique"
        ],
        "exact_saved_ip_matches": counts["saved_ip"],
        "local_status_dp_matches": counts["status_dp"],
        "local_status_match": status_match,
        "shared_account_identity_matches": 0,
        "matching_order": [
            "exact UDP deviceId",
            "exact UDP UUID",
            "exact UDP MAC",
            "exact UDP node/gateway/parent ID",
            "unique UDP productKey + protocol version",
            "unique UDP productKey",
            "exact saved private IP",
            "read-only local status() deviceId+localKey+DP overlap",
            "shared-account exact metadata",
        ],
    })

    print(
        "[LAN] Current local Tuya hosts="
        f"{model['lan_scan']['current_lan_tuya_hosts']}; "
        "exact device identities="
        f"{model['lan_scan']['matched_account_devices']}; "
        "unresolved local hosts="
        f"{model['lan_scan']['unresolved_local_host_count']}; "
        "UDP identity rows="
        f"{len(udp_rows)}; status comparison="
        f"{counts['status_dp']} matches / {status_match.get('attempts', 0)} probes.",
        flush=True,
    )
    return model


def apply_shared_account_identity_matches(model, account):
    """
    Complete unresolved mappings from the single shared-account snapshot.
    No local status() request is used.
    """
    account_rows = (
        account.get("devices")
        if isinstance(account, dict)
        else []
    )
    if not isinstance(account_rows, list):
        return model

    nmap_rows = model.get(
        "lan_scan",
        {},
    ).get("nmap_candidates", [])
    nmap_by_ip = {
        private_ip(row.get("ip")): row
        for row in nmap_rows
        if private_ip(row.get("ip"))
    }
    nmap_by_mac = {
        norm_mac(row.get("mac")): row
        for row in nmap_rows
        if norm_mac(row.get("mac"))
    }

    devices = model.get("devices", [])
    indexes = _identity_indexes(devices)

    matches = {}
    for device in devices:
        if (
            device.get("current_lan_match")
            and private_ip(device.get("lan_ip"))
        ):
            matches[txt(device.get("tuya_id"))] = {
                "ip": private_ip(device.get("lan_ip")),
                "method": device.get("local_match_method"),
                "version": device.get(
                    "protocol_version"
                ),
                "nmap_mac": norm_mac(
                    device.get(
                        "lan_discovery",
                        {},
                    ).get("nmap_mac")
                    or device.get("mac")
                ),
                "status_used": bool(
                    device.get("lan_discovery", {}).get("status_used")
                    or device.get("local_match_method") == "local_status_deviceId_localKey_dp_overlap"
                ),
            }

    claimed_ids = set(matches)
    claimed_ips = {
        private_ip(match.get("ip"))
        for match in matches.values()
        if private_ip(match.get("ip"))
    }

    added = 0

    for row in account_rows:
        row_id = txt(first(
            row.get("deviceId"),
            row.get("device_id"),
            row.get("id"),
        ))
        row_uuid = txt(row.get("uuid"))
        row_mac = norm_mac(first(
            row.get("mac"),
            row.get("macAddress"),
            row.get("mac_address"),
        ))
        row_ip = private_ip(first(
            row.get("ip"),
            row.get("local_ip"),
            row.get("localIp"),
        ))

        device = (
            _unique_index_match(
                indexes["device_id"],
                row_id,
            )
            or _unique_index_match(
                indexes["uuid"],
                row_uuid,
            )
            or _unique_index_match(
                indexes["mac"],
                row_mac,
            )
            or _unique_index_match(
                indexes["node_id"],
                first(
                    row.get("node_id"),
                    row.get("nodeId"),
                ),
            )
            or _unique_index_match(
                indexes["gateway_id"],
                first(
                    row.get("gateway_id"),
                    row.get("gatewayId"),
                    row.get("gw_id"),
                    row.get("gwId"),
                ),
            )
            or _unique_index_match(
                indexes["parent_id"],
                first(
                    row.get("parent_id"),
                    row.get("parentId"),
                ),
            )
        )

        if device is None:
            product = txt(first(
                row.get("product_id"),
                row.get("productId"),
                row.get("productKey"),
            ))
            version = txt(first(
                row.get("protocolVersion"),
                row.get("version"),
            ))
            if product and version:
                device = _unique_index_match(
                    indexes["product_version"],
                    product.lower()
                    + "|"
                    + version.lower(),
                )
            if device is None and product:
                device = _unique_index_match(
                    indexes["product_key"],
                    product,
                )

        if device is None:
            continue

        device_id = txt(device.get("tuya_id"))
        if not device_id or device_id in claimed_ids:
            continue

        nmap_row = None
        if row_ip in nmap_by_ip:
            nmap_row = nmap_by_ip[row_ip]
        elif row_mac in nmap_by_mac:
            nmap_row = nmap_by_mac[row_mac]
        else:
            device_ip = private_ip(device.get("lan_ip"))
            device_mac = norm_mac(device.get("mac"))
            if device_ip in nmap_by_ip:
                nmap_row = nmap_by_ip[device_ip]
            elif device_mac in nmap_by_mac:
                nmap_row = nmap_by_mac[device_mac]

        if nmap_row is None:
            continue

        ip = private_ip(nmap_row.get("ip"))
        if not ip or ip in claimed_ips:
            continue

        matches[device_id] = {
            "ip": ip,
            "method": "shared_account_exact_identity",
            "version": first(
                row.get("protocolVersion"),
                row.get("version"),
                device.get("protocol_version"),
            ),
            "nmap_mac": norm_mac(nmap_row.get("mac")),
        }
        claimed_ids.add(device_id)
        claimed_ips.add(ip)
        added += 1

        device["uuid"] = first(
            device.get("uuid"),
            row.get("uuid"),
        )
        device["node_id"] = first(
            device.get("node_id"),
            row.get("node_id"),
            row.get("nodeId"),
        )
        device["gateway_id"] = first(
            device.get("gateway_id"),
            row.get("gateway_id"),
            row.get("gatewayId"),
            row.get("gw_id"),
            row.get("gwId"),
        )
        device["parent_id"] = first(
            device.get("parent_id"),
            row.get("parent_id"),
            row.get("parentId"),
        )
        device["mac"] = first(
            device.get("mac"),
            row_mac,
        )

    _apply_lan_matches(
        model,
        nmap_rows,
        matches,
        "udp_nmap_plus_shared_account",
    )

    model["lan_scan"][
        "shared_account_identity_matches"
    ] = added
    model["lan_scan"][
        "status_used_for_matching"
    ] = bool(
        model.get("lan_scan", {}).get("status_used_for_matching")
        or any(match.get("status_used") for match in matches.values())
    )

    print(
        "[LAN] Final mapping after shared account: "
        "current local Tuya hosts="
        f"{model['lan_scan']['current_lan_tuya_hosts']}; "
        "exact device identities="
        f"{model['lan_scan']['matched_account_devices']}; "
        "unresolved local hosts="
        f"{model['lan_scan']['unresolved_local_host_count']}; "
        "status comparison=NO.",
        flush=True,
    )
    return model


def helper_path():
    here=pathlib.Path(__file__).resolve().parent
    for p in [here/"monik_local_tinytuya_control.py",here.parent/"monik_local_tinytuya_control.py"]:
        if p.is_file(): return p
    return None




def local_execute(device, actions):
    if not device.get("current_lan_match"):
        raise ValueError("Local data exists, but no exact current-LAN identity match was found.")
    ip = private_ip(device.get("lan_ip"))
    if not ip:
        raise ValueError(
            "Local control data exists, but this device was not found on the current LAN."
        )
    key = txt(device.get("local_key"))
    device_id = txt(device.get("tuya_id"))
    if not ip:
        raise ValueError("Local command unavailable: no private LAN IP is known.")
    if not key:
        raise ValueError("Local command unavailable: localKey is missing.")
    if not device_id:
        raise ValueError("Local command unavailable: Tuya deviceId is missing.")

    helper = helper_path()
    version = txt(device.get("protocol_version") or "3.3")
    results = []

    if helper:
        for action in actions:
            if action.get("dp_id") is None:
                raise ValueError(
                    "No numeric DP ID exists in the selected JSON for "
                    + txt(action.get("logical_code") or action.get("code"))
                )
            run = subprocess.run(
                [
                    sys.executable, str(helper),
                    "--ip", ip,
                    "--id", device_id,
                    "--key", key,
                    "--version", version,
                    "--dp", str(action["dp_id"]),
                    "--value", json.dumps(
                        action.get("value"),
                        ensure_ascii=False,
                    ),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=45,
            )
            results.append({
                "logical_code": action.get("logical_code"),
                "code": action.get("code"),
                "dp_id": action.get("dp_id"),
                "exit_code": run.returncode,
                "stdout": run.stdout,
                "stderr": run.stderr,
            })
            if run.returncode:
                break
        return {
            "success": all(item["exit_code"] == 0 for item in results),
            "transport": "existing monik_local_tinytuya_control.py",
            "lan_ip": ip,
            "device_id": device_id,
            "protocol_version": version,
            "external_ip_checked": False,
            "results": results,
        }

    if importlib.util.find_spec("tinytuya"):
        import tinytuya  # type: ignore
        obj = tinytuya.Device(device_id, ip, key)
        try:
            obj.set_version(float(version))
        except Exception:
            obj.set_version(3.3)

        for action in actions:
            if action.get("dp_id") is None:
                raise ValueError(
                    "No numeric DP ID exists in the selected JSON for "
                    + txt(action.get("logical_code") or action.get("code"))
                )
            results.append({
                "logical_code": action.get("logical_code"),
                "code": action.get("code"),
                "dp_id": action.get("dp_id"),
                "result": obj.set_value(
                    int(action["dp_id"]),
                    action.get("value"),
                ),
            })
        return {
            "success": True,
            "transport": "existing local tinytuya module",
            "lan_ip": ip,
            "device_id": device_id,
            "protocol_version": version,
            "external_ip_checked": False,
            "results": results,
        }

    raise RuntimeError(
        "No existing local Tuya transport was found. Nothing was installed."
    )


def get_device(pid):
    with LOCK:
        for d in STATE["model"].get("devices",[]):
            if d.get("physical_id")==pid:return d
    raise KeyError("Physical device not found")


def get_control(device,code):
    for c in device.get("controls",[]):
        if c.get("code")==code:return c
    raise KeyError("Control not found")


def actions_for(control, value):
    if control.get("virtual"):
        actions = []
        seen = set()
        for row in control.get("virtual_actions", []):
            code = row.get("code")
            dp_id = row.get("dp_id")
            key = (code, dp_id)
            if not code or key in seen:
                continue
            seen.add(key)
            actions.append({
                "code": code,
                "logical_code": row.get("logical_code"),
                "dp_id": dp_id,
                "value": value,
            })
        return actions

    return [{
        "code": first(control.get("command_code"), control.get("code")),
        "logical_code": control.get("code"),
        "dp_id": control.get("dp_id"),
        "value": coerce_control_value(control, value),
    }]


def ypayload(control,value,index=0):
    arr=control.get("yandex_actions") or []
    if not arr: raise ValueError("No Yandex mapping for this control")
    a=arr[index if isinstance(index,int) and 0<=index<len(arr) else 0]
    return {"devices":[{"id":a.get("device_id"),"actions":[{"type":a.get("type"),"state":{"instance":a.get("instance"),"value":value}}]}]}

HTML=r'''<!doctype html><html lang="bg"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MoniK Universal Builder</title><script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script><style>
:root{color-scheme:dark;--bg:#090d14;--p:#121925;--p2:#182231;--l:#2b394d;--t:#edf4ff;--m:#94a6bd;--b:#2d7ff9;--g:#1f9d64;--r:#d84a4a;--u:#805ad5;--y:#168aad}*{box-sizing:border-box}body{margin:0;background:linear-gradient(160deg,#080b11,#101827);color:var(--t);font-family:Segoe UI,Arial}header{position:sticky;top:0;z-index:20;background:#090d14f3;border-bottom:1px solid var(--l);padding:14px 18px}h1{font-size:21px;margin:0 0 10px}.bar{display:flex;gap:8px;flex-wrap:wrap}button,input,textarea{font:inherit;color:var(--t);background:var(--p2);border:1px solid var(--l);border-radius:8px;padding:8px 10px}button{cursor:pointer}.primary{background:var(--b)}.local{background:var(--g)}.tuya{background:var(--u)}.yandex{background:var(--y)}.danger{background:#6e2525}.plan{background:#34445a}button:disabled{opacity:.4}#search{min-width:220px;flex:1}.meta{font-size:12px;color:var(--m);margin-top:9px}main{padding:16px;display:grid;gap:13px}.welcome,.device{background:var(--p);border:1px solid var(--l);border-radius:13px;padding:15px}.head{display:flex;justify-content:space-between;gap:12px}.device h2{font-size:18px;margin:0}.ids{font:12px Consolas;color:var(--m);word-break:break-all}.badges,.routes{display:flex;gap:5px;flex-wrap:wrap;margin:8px 0}.badge{font-size:11px;border:1px solid var(--l);background:#233044;border-radius:999px;padding:3px 7px}.ok{background:#153f2e}.bad{background:#4a1f24}.coverage{display:grid;grid-template-columns:repeat(auto-fit,minmax(125px,1fr));gap:7px}.metric{background:#0d141e;border:1px solid var(--l);border-radius:8px;padding:8px}.metric b{font-size:18px;display:block}.metric span{font-size:11px;color:var(--m)}.warning{background:#392814;border:1px solid #765021;padding:8px;border-radius:8px;margin:6px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:10px;margin-top:12px}.control{background:#0e1621;border:1px solid var(--l);border-radius:10px;padding:11px}.virtual{border-color:#7056a5}.ct{font-weight:700}.cc{font:11px Consolas;color:var(--m);word-break:break-all}.state{font-size:12px;margin:6px 0}.controls{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-top:7px}.controls input[type=range]{min-width:140px;flex:1}.controls input[type=number]{width:95px}.controls textarea{width:100%;min-height:75px;font:12px Consolas}.result,pre{background:#070b10;border:1px solid var(--l);border-radius:7px;padding:8px;max-height:280px;overflow:auto;white-space:pre-wrap;word-break:break-word;font:11px Consolas}.modal{position:fixed;inset:0;background:#000b;display:none;align-items:center;justify-content:center;z-index:50;padding:20px}.modal.open{display:flex}.modalCard{width:min(620px,100%);background:var(--p);border:1px solid var(--l);border-radius:14px;padding:18px;text-align:center}#qr{display:inline-block;background:#fff;padding:16px;border-radius:9px}.hidden{display:none!important}@media(max-width:700px){header{position:static}.head{display:block}.grid{grid-template-columns:1fr}}</style></head><body>
<header><h1>MoniK — Tuya Account Schema + Real LAN Discovery + Status</h1><div class="bar"><input id="file" type="file" accept=".json,application/json"><button id="load" class="primary">Browse JSON и построи</button><input id="search" placeholder="Търси устройство, код, ID..."><button id="connect" class="tuya">Свържи ОТНОВО Tuya — само при ревокирана сесия</button><button id="status">Remote status</button><button id="arp" class="local">SCAN LOCAL TUYA + ARP</button><button id="download">Download модел</button><button id="stop" class="danger">Спри</button></div><div id="meta" class="meta">Избери един JSON. Няма сканиране на архиви.</div></header><main id="root"><section class="welcome"><b>Ръчно избираш един JSON. Строят се само схемите и точните кодове в него.</b><p>След схемата се прави LAN/ARP проверка, локалните устройства се подреждат отпред и status() се прочита точно веднъж при първото зареждане. Няма автоматично включване, изключване, refresh, DP discovery или пробна команда.</p></section></main>
<div id="modal" class="modal"><div class="modalCard"><h2>Tuya Smart / Smart Life</h2><div id="form"><p>User Code: Me → Settings → Account and Security → User Code</p><div class="controls" style="justify-content:center"><input id="uc" placeholder="Tuya User Code"><button id="start" class="tuya">Генерирай QR</button></div></div><div id="qa" class="hidden"><p>Сканирай и потвърди.</p><div id="qr"></div><div id="qs">Изчакване...</div></div><button id="close">Затвори</button></div></div>
<script>"use strict";let M=null,P=null;const $=x=>document.getElementById(x),esc=s=>String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[m])),pretty=v=>JSON.stringify(v,null,2);async function api(p,o={}){let r=await fetch(p,{cache:"no-store",headers:{"Content-Type":"application/json",...(o.headers||{})},...o}),d=await r.json();if(!r.ok)throw Error(d.error||pretty(d));return d}function result(b,v,e=false){b.textContent=typeof v==="string"?v:pretty(v);b.style.borderColor=e?"#b63b49":"#2b6e50"}async function load(){let f=$("file").files[0];if(!f)return alert("Избери JSON");$("meta").textContent="Построяване...";try{M=await api("/api/load",{method:"POST",body:JSON.stringify({name:f.name,text:await f.text()})});render();try{let once=await api("/api/initial-status",{method:"POST",body:"{}"});M=once;render();if(M.initial_status_error)$("meta").textContent+=" | TUYA ERROR: "+M.initial_status_error}catch(e){$("meta").textContent+=" | TUYA ERROR: "+e}}catch(e){$("meta").textContent="ГРЕШКА: "+e}}function rb(t,c,en,fn){let b=document.createElement("button");b.textContent=t;b.className=c;b.disabled=!en;b.onclick=fn;return b}function editor(c,h,cb){let k=c.kind,cur=c.current,s=c.values||{};if(k==="boolean"){let r=document.createElement("div");r.className="controls";let a=rb("ON","local",true,()=>cb(true)),b=rb("OFF","danger",true,()=>cb(false));r.append(a,b);h.append(r);return}if(k==="number"){let min=Number.isFinite(Number(s.min))?Number(s.min):0,max=Number.isFinite(Number(s.max))?Number(s.max):100,step=Number(s.step||s.precision||1)||1,val=Number.isFinite(Number(cur))?Number(cur):min,r=document.createElement("div");r.className="controls";let x=document.createElement("input");x.type="range";x.min=min;x.max=max;x.step=step;x.value=val;let n=document.createElement("input");n.type="number";n.min=min;n.max=max;n.step=step;n.value=val;x.oninput=()=>n.value=x.value;n.oninput=()=>x.value=n.value;r.append(x,n,rb("Използвай","plan",true,()=>cb(Number(n.value))));h.append(r);return}let range=Array.isArray(s.range)?s.range:[];if(k==="enum"&&range.length){let r=document.createElement("div");r.className="controls";for(let v of range)r.append(rb(String(v),"",true,()=>cb(v)));h.append(r);return}let a=document.createElement("textarea");a.value=cur==null?"":(typeof cur==="string"?cur:pretty(cur));let r=document.createElement("div");r.className="controls";r.append(rb("Използвай exact value","plan",true,()=>{let v=a.value;try{v=JSON.parse(v)}catch{}cb(v)}));h.append(a,r)}function panel(d,c,h,v){for(let x of h.querySelectorAll(".routes,.result"))x.remove();let r=document.createElement("div");r.className="routes";let o=document.createElement("div");o.className="result";o.textContent="value: "+pretty(v);r.append(rb("PLAN","plan",true,async()=>{try{result(o,await api("/api/plan",{method:"POST",body:JSON.stringify({physical_id:d.physical_id,code:c.code,value:v})}))}catch(e){result(o,String(e),true)}}),rb("MANUAL LOCAL TEST","local",Boolean(c.routes&&c.routes.local),async()=>{if(!confirm("Да се изпрати избраната LOCAL команда сега?"))return;try{result(o,await api("/api/local",{method:"POST",body:JSON.stringify({physical_id:d.physical_id,code:c.code,value:v})}))}catch(e){result(o,String(e),true)}}),rb("MANUAL TUYA TEST","tuya",Boolean(d.tuya_id&&(c.command_code||c.code)),async()=>{if(!confirm(`Send TUYA CLOUD command?\n${d.name}\n${c.code} = ${JSON.stringify(v)}`))return;try{result(o,await api("/api/tuya",{method:"POST",body:JSON.stringify({physical_id:d.physical_id,code:c.code,value:v})}))}catch(e){result(o,String(e),true)}}),rb("MANUAL YANDEX TEST","yandex",c.routes.yandex,async()=>{if(!confirm("Да се изпрати избраната YANDEX команда сега?"))return;try{result(o,await api("/api/yandex",{method:"POST",body:JSON.stringify({physical_id:d.physical_id,code:c.code,value:v})}))}catch(e){result(o,String(e),true)}}));h.append(r,o)}function rc(d,c){let b=document.createElement("section");b.className="control"+(c.virtual?" virtual":"");b.innerHTML='<div class="ct">'+esc(c.name)+'</div><div class="cc">'+esc(c.code)+' | '+esc(c.type||c.kind)+'</div><div class="state">current: '+esc(pretty(c.current))+'</div>';editor(c,b,v=>panel(d,c,b,v));let z=document.createElement("div");z.className="badges";for(let [k,v] of Object.entries(c.routes))z.innerHTML+='<span class="badge '+(v?'ok':'bad')+'">'+esc(k)+': '+(v?'ready':'no')+'</span>';b.append(z);let de=document.createElement("details");de.innerHTML='<summary>Schema / mapping</summary><pre>'+esc(pretty(c))+'</pre>';b.append(de);return b}function render(){if(!M)return;let q=$("search").value.trim().toLowerCase();let a=M.arp_scan||{},l=M.lan_scan||{},s=M.local_status_once||{};$("meta").textContent=`Файл: ${M.source_name} | Devices: ${M.physical_device_count} | Current LAN Tuya hosts: ${l.current_lan_tuya_hosts||l.open_6668_count||0} | Exact device identities: ${l.matched_account_devices||0} | Unresolved LAN hosts: ${l.unresolved_local_host_count||0} | UDP identity rows: ${l.udp_identity_row_count||0} | Tuya account: ${(M.tuya_account&&M.tuya_account.device_count)||0}${M.tuya_account&&M.tuya_account.error?' ERROR':''}`;let root=$("root");root.innerHTML="";
let table=document.createElement("table");
table.style.width="100%";table.style.borderCollapse="collapse";table.style.marginBottom="14px";
table.innerHTML='<thead><tr><th style="text-align:left;padding:8px;border:1px solid var(--l)">Device</th><th style="text-align:left;padding:8px;border:1px solid var(--l)">deviceId</th><th style="text-align:left;padding:8px;border:1px solid var(--l)">LAN IP</th><th style="text-align:left;padding:8px;border:1px solid var(--l)">LOCAL DATA</th><th style="text-align:left;padding:8px;border:1px solid var(--l)">CURRENT LAN</th><th style="text-align:left;padding:8px;border:1px solid var(--l)">TUYA CLOUD</th><th style="text-align:left;padding:8px;border:1px solid var(--l)">ONLINE</th><th style="text-align:left;padding:8px;border:1px solid var(--l)">YANDEX</th><th style="text-align:left;padding:8px;border:1px solid var(--l)">CONTROLS</th></tr></thead>';
let tbody=document.createElement("tbody");
for(let d of M.devices){
  let localData=d.controls.some(c=>c.routes&&c.routes.local);
  let localNow=d.controls.some(c=>c.routes&&c.routes.local_current);
  let tuyaCapable=Boolean(d.tuya_id&&d.controls.some(c=>c.command_code||c.code));
  let tuyaReady=d.tuya_shared===true;
  let tuyaPending=d.tuya_shared===null||d.tuya_shared===undefined;
  let yandexReady=d.controls.some(c=>c.routes&&c.routes.yandex);
  let tr=document.createElement("tr");
  tr.innerHTML='<td style="padding:8px;border:1px solid var(--l)">'+esc(d.name)+'</td>'+
    '<td style="padding:8px;border:1px solid var(--l);font-family:Consolas">'+esc(d.tuya_id||'—')+'</td>'+
    '<td style="padding:8px;border:1px solid var(--l)">'+esc(d.lan_ip||'—')+'</td>'+
    '<td style="padding:8px;border:1px solid var(--l)" class="'+(localData?'ok':'bad')+'">'+(localData?'READY':'MISSING')+'</td>'+
    '<td style="padding:8px;border:1px solid var(--l)" class="'+(localNow||d.same_external_ip_group?'ok':'bad')+'">'+(localNow?'CONNECTED':(d.same_external_ip_group?'SAME WAN / NEED IP':'OTHER NETWORK'))+'</td>'+
    '<td style="padding:8px;border:1px solid var(--l)" class="'+(tuyaReady?'ok':(tuyaPending?'':'bad'))+'">'+(tuyaReady?'READY':(tuyaPending&&tuyaCapable?'PENDING':(tuyaCapable?'ACCOUNT ERROR':'MISSING')))+'</td>'+
    '<td style="padding:8px;border:1px solid var(--l)" class="'+(d.tuya_online===true?'ok':(d.tuya_online===false?'bad':''))+'">'+(d.tuya_online===true?'ONLINE':(d.tuya_online===false?'OFFLINE':'UNKNOWN'))+'</td>'+
    '<td style="padding:8px;border:1px solid var(--l)" class="'+(yandexReady?'ok':'bad')+'">'+(yandexReady?'READY':'NO')+'</td>'+
    '<td style="padding:8px;border:1px solid var(--l)">'+d.controls.length+'</td>';
  tbody.append(tr);
}
table.append(tbody);root.append(table);
for(let d of M.devices){if(q&&!pretty(d).toLowerCase().includes(q))continue;let card=document.createElement("article");card.className="device";card.innerHTML='<div class="head"><div><h2>'+esc(d.name)+'</h2><div class="ids">physical='+esc(d.physical_id)+'<br>tuya='+esc(d.tuya_id||'—')+'</div></div><div class="badges"><span class="badge">'+esc(d.category||'no category')+'</span><span class="badge">'+esc(d.product_id||'no productId')+'</span><span class="badge '+(d.has_local_key?'ok':'bad')+'">LOCAL DATA '+(d.has_local_key?'READY':'MISSING')+'</span><span class="badge '+(d.current_lan_match||d.same_external_ip_group?'ok':'bad')+'">CURRENT LAN '+(d.current_lan_match?esc(d.lan_ip||'CONNECTED'):(d.same_external_ip_group?'SAME WAN / NEED IP':'OTHER NETWORK'))+'</span></div></div>';let cov=document.createElement("div");cov.className="coverage";for(let [k,v] of Object.entries(d.coverage))cov.innerHTML+='<div class="metric"><b>'+esc(v)+'</b><span>'+esc(k)+'</span></div>';card.append(cov);for(let w of d.warnings||[]){let x=document.createElement("div");x.className="warning";x.textContent=w;card.append(x)}let g=document.createElement("div");g.className="grid";for(let c of d.controls)g.append(rc(d,c));card.append(g);let de=document.createElement("details");de.innerHTML='<summary>Построен модел / endpoints / status</summary><pre>'+esc(pretty({logical_endpoints:d.logical_endpoints,status_from_json:d.status,lan_discovery:d.lan_discovery,first_local_status:d.local_status_once,schema_channel_count:d.schema_channel_count,coverage:d.coverage,warnings:d.warnings}))+'</pre>';card.append(de);root.append(card)}}function open(){ $("modal").classList.add("open");$("form").classList.remove("hidden");$("qa").classList.add("hidden");$("qr").innerHTML=""}function close(){ $("modal").classList.remove("open");if(P){clearInterval(P);P=null}}async function start(){let u=$("uc").value.trim();if(!u)return alert("Въведи User Code");try{let r=await api("/api/qr/start",{method:"POST",body:JSON.stringify({user_code:u})});$("form").classList.add("hidden");$("qa").classList.remove("hidden");$("qr").innerHTML="";new QRCode($("qr"),{text:r.qr_payload,width:340,height:340,correctLevel:QRCode.CorrectLevel.M});$("qs").textContent="Сканирай и потвърди...";P=setInterval(async()=>{try{let s=await api("/api/qr/poll",{method:"POST",body:"{}"});if(s.approved){clearInterval(P);P=null;$("qr").innerHTML="";if(s.model){M=s.model;render()}$("qs").textContent=`Tuya account connected: ${s.device_count||0} devices. The MoniK server session is saved and reused automatically.`}else $("qs").textContent="Изчакване: "+(s.msg||s.code||"pending")}catch(e){$("qs").textContent=String(e)}},2000)}catch(e){alert(String(e))}}function download(){if(!M)return alert("Зареди JSON");let b=new Blob([pretty(M)],{type:"application/json"}),a=document.createElement("a");a.href=URL.createObjectURL(b);a.download="MONIK_UNIVERSAL_BUILT_MODEL.json";a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}$("load").onclick=load;$("search").oninput=render;$("connect").onclick=open;$("status").onclick=async()=>{try{$("meta").textContent="Refreshing the manually shared Tuya account...";let r=await api("/api/tuya/status",{method:"POST",body:"{}"});if(r.model){M=r.model;render()}else $("meta").textContent=pretty(r)}catch(e){$("meta").textContent="Tuya account refresh error: "+e.message}};$("arp").onclick=async()=>{try{$("meta").textContent="Tuya LAN discovery + Nmap + exact account identity comparison...";M=await api("/api/arp");render()}catch(e){alert(String(e))}};$("close").onclick=close;$("start").onclick=start;$("download").onclick=download;$("stop").onclick=async()=>{try{await api("/api/stop",{method:"POST",body:"{}"})}catch{}document.body.innerHTML='<h2 style="padding:30px">Сървърът е спрян.</h2>'};</script></body></html>'''



def apply_account_snapshot(model: dict, account: dict) -> dict:
    model = merge_tuya_account(model, account)
    model = apply_shared_account_identity_matches(model, account)
    online_by_id = {}
    for row in account.get("devices", []):
        device_id = txt(row.get("id") or row.get("deviceId") or row.get("device_id"))
        if device_id:
            value = row.get("online")
            online_by_id[device_id] = bool(value) if value is not None else None
    for device in model.get("devices", []):
        device["tuya_online"] = online_by_id.get(txt(device.get("tuya_id")))
    model.setdefault("tuya_account", {})["one_time_status_pending"] = False
    return model


def start_tuya_account_job() -> dict:
    event = threading.Event()
    box = {}

    def worker():
        try:
            box["account"] = REMOTE.request(
                "tuya_account",
                timeout=90,
            )
        except Exception as exc:
            box["error"] = str(exc)
        finally:
            event.set()

    job = {"event": event, "box": box}
    threading.Thread(target=worker, daemon=True).start()
    return job

def finish_tuya_account_job(job: dict, wait_seconds: float) -> tuple[dict | None, str | None]:
    if not isinstance(job, dict):
        return None, "Tuya account job is missing"
    event = job.get("event")
    box = job.get("box") or {}
    if isinstance(event, threading.Event):
        event.wait(timeout=max(0.0, wait_seconds))
        if not event.is_set():
            return None, None
    return box.get("account"), box.get("error")


class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args): print("[WEB] "+fmt%args,flush=True)
    def sendb(self,status,ctype,body): self.send_response(status);self.send_header("Content-Type",ctype);self.send_header("Content-Length",str(len(body)));self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(body)
    def sendj(self,status,value): self.sendb(status,"application/json; charset=utf-8",json.dumps(value,ensure_ascii=False,indent=2).encode())
    def body(self):
        n=int(self.headers.get("Content-Length","0") or 0)
        if n<0 or n>MAX_UPLOAD: raise ValueError("Request body too large")
        value=json.loads(self.rfile.read(n).decode() or "{}")
        if not isinstance(value,dict): raise ValueError("JSON object required")
        return value
    def do_GET(self):
        try:
            p=urllib.parse.urlsplit(self.path).path
            if p=="/": return self.sendb(200,"text/html; charset=utf-8",HTML.encode())
            if p=="/api/status": return self.sendj(200,REMOTE.request("status"))
            if p=="/api/arp":
                with LOCK:
                    STATE["model"]=apply_arp(STATE["model"])
                    return self.sendj(200,public_model(STATE["model"]))
            self.sendj(404,{"error":"Not found"})
        except Exception as e: self.sendj(500,{"error":str(e),"traceback":traceback.format_exc()})
    def do_POST(self):
        try:
            p=urllib.parse.urlsplit(self.path).path
            if p=="/api/load":
                b = self.body()
                raw = json.loads(b.get("text") or "")

                # Only the proven STRATO sharing session is used.
                # Device JSON is schema/data only and cannot replace the token.
                account_job = start_tuya_account_job()

                model = apply_arp(
                    build(
                        raw,
                        txt(b.get("name")) or "browser.json",
                    )
                )

                for device in model.get("devices", []):
                    device["tuya_online"] = None
                    device["tuya_shared"] = None

                model["tuya_account"] = {
                    "connected": None,
                    "device_count": 0,
                    "one_time_status_pending": True,
                    "session_file": (
                        "/opt/monik-tuya-auth/"
                        "device-sharing-session.json"
                    ),
                    "selected_json_may_not_replace_session": True,
                }

                account, account_error = finish_tuya_account_job(
                    account_job,
                    0.10,
                )
                if isinstance(account, dict):
                    model = apply_account_snapshot(model, account)

                with LOCK:
                    STATE["model"] = model
                    STATE["tuya_account"] = account
                    STATE["tuya_account_job"] = account_job

                print(
                    "[WEB] Full schema returned; proven V6 Tuya "
                    "session and LAN identity scan are independent.",
                    flush=True,
                )
                return self.sendj(200, public_model(model))

            if p=="/api/initial-status":
                self.body()
                with LOCK:
                    cached = STATE.get("tuya_account")
                    job = STATE.get("tuya_account_job")
                    if isinstance(cached, dict):
                        return self.sendj(
                            200,
                            public_model(STATE["model"]),
                        )

                account, account_error = finish_tuya_account_job(
                    job,
                    90.0,
                )
                if isinstance(account, dict):
                    with LOCK:
                        STATE["tuya_account"] = account
                        STATE["model"] = apply_account_snapshot(
                            STATE["model"],
                            account,
                        )
                        result_model = public_model(
                            STATE["model"]
                        )
                    return self.sendj(200, result_model)

                error_text = (
                    account_error
                    or "Tuya sharing account returned no snapshot"
                )
                with LOCK:
                    STATE["model"]["tuya_account"] = {
                        "connected": False,
                        "device_count": 0,
                        "one_time_status_pending": False,
                        "error": error_text,
                        "session_file": (
                            "/opt/monik-tuya-auth/"
                            "device-sharing-session.json"
                        ),
                    }
                    result_model = public_model(STATE["model"])

                print(
                    "[TUYA] ACCOUNT ERROR: " + error_text,
                    flush=True,
                )
                return self.sendj(
                    200,
                    {
                        **result_model,
                        "initial_status_error": error_text,
                    },
                )

            if p in {"/api/plan","/api/local","/api/tuya","/api/yandex"}:
                b=self.body(); d=get_device(txt(b.get("physical_id"))); c=get_control(d,txt(b.get("code"))); value=b.get("value"); acts=actions_for(c,value); plan={"physical_id":d.get("physical_id"),"device_name":d.get("name"),"tuya_device_id":d.get("tuya_id"),"control_code":c.get("code"),"virtual":bool(c.get("virtual")),"value":value,"exact_tuya_commands":[{"code":a.get("code"),"value":a.get("value")} for a in acts],"exact_local_dp_actions":acts,"yandex_mappings":c.get("yandex_actions") or [],"routes":c.get("routes"),"safety":{"lan_ip":d.get("lan_ip"),"external_ip":d.get("external_ip"),"has_local_key":bool(d.get("local_key"))}}
                if p=="/api/plan": return self.sendj(200,plan)
                if p=="/api/local": return self.sendj(200,{"plan":plan,"result":local_execute(d,acts)})
                if p=="/api/tuya":
                    if not d.get("tuya_id"):
                        raise ValueError("Tuya deviceId missing")
                    if not acts or not all(txt(a.get("code")) for a in acts):
                        raise ValueError("Tuya command code missing")

                    commands = [
                        {
                            "code": action.get("code"),
                            "value": action.get("value"),
                        }
                        for action in acts
                    ]
                    result_value = REMOTE.request(
                        "tuya_command",
                        timeout=20,
                        device_id=d.get("tuya_id"),
                        commands=commands,
                    )
                    return self.sendj(
                        200,
                        {
                            "plan": plan,
                            "result": result_value,
                            "tuya_account_device_count": (
                                STATE.get("tuya_account") or {}
                            ).get("device_count", 0),
                            "tuya_session_source": (
                                "/opt/monik-tuya-auth/"
                                "device-sharing-session.json"
                            ),
                            "strato_session_file_updates_only": True,
                            "strato_installs": False,
                        },
                    )
                payload=ypayload(c,value,b.get("yandex_action_index",0)); r=REMOTE.request("yandex_action",payload=payload); return self.sendj(200 if r.get("ok") else 502,{"plan":plan,"payload":payload,"result":r,"strato_writes":False,"strato_installs":False})
            if p=="/api/qr/start": return self.sendj(200,REMOTE.request("tuya_qr_start",user_code=txt(self.body().get("user_code"))))
            if p=="/api/qr/poll":
                self.body(); response=REMOTE.request("tuya_qr_poll",timeout=180)
                if response.get("approved"):
                    account=response.pop("account",None)
                    if not isinstance(account,dict): raise RuntimeError("Tuya approved the QR login but returned no account snapshot")
                    with LOCK:
                        STATE["tuya_account"]=account
                        STATE["model"]=merge_tuya_account(STATE["model"],account)
                        response["model"]=public_model(STATE["model"])
                    response["device_count"]=account.get("device_count",0)
                    response["home_count"]=account.get("home_count",0)
                return self.sendj(200,response)
            if p=="/api/tuya/status":
                self.body(); account=REMOTE.request("tuya_account",timeout=180)
                with LOCK:
                    STATE["tuya_account"] = account
                    STATE["model"] = apply_account_snapshot(
                        STATE["model"],
                        account,
                    )
                    return self.sendj(200,{"connected":True,"device_count":account.get("device_count",0),"home_count":account.get("home_count",0),"model":public_model(STATE["model"])})
            if p=="/api/stop": self.body(); self.sendj(200,{"stopping":True}); threading.Thread(target=self.server.shutdown,daemon=True).start(); return
            self.sendj(404,{"error":"Not found"})
        except (ValueError,KeyError,json.JSONDecodeError) as e: self.sendj(400,{"error":str(e)})
        except Exception as e: self.sendj(500,{"error":str(e),"traceback":traceback.format_exc()})


def main():
    print("="*76);print(APP_TITLE);print("="*76);print("NO archive scan\nNO installs\nOne selected JSON is rebuilt in memory\nExisting Tuya sharing session on MoniK server is reused automatically\nNo new QR pairing unless that stored session is missing or revoked\nOnly the same Tuya session file is updated when Tuya rotates the refresh token\nLocal deviceId + localKey + DP data from the selected JSON remains valid\nYandex uses STRATO only if a manual Yandex action is pressed\n")
    server=None
    for port in range(8765,8776):
        try: server=ThreadingHTTPServer(("127.0.0.1",port),Handler);break
        except OSError: pass
    if server is None: raise RuntimeError("No free port 8765..8775")
    url=f"http://127.0.0.1:{server.server_address[1]}/";print("[WEB] "+url,flush=True);threading.Timer(.7,lambda:webbrowser.open(url)).start()
    try: server.serve_forever(poll_interval=.3)
    except KeyboardInterrupt: pass
    finally: REMOTE.stop();server.server_close()
    return 0

if __name__=="__main__": raise SystemExit(main())
