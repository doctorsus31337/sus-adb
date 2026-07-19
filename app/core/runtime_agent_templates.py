"""Deterministic, transparent Frida JavaScript templates."""
from __future__ import annotations

import json
from typing import Any


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _header(kind: str, metadata: dict[str, Any]) -> str:
    return "// SUS-ADB Runtime Explorer\n// Kind: " + kind + "\n// Metadata: " + _json(metadata) + "\n'use strict';\n"


def readiness_probe() -> str:
    return _header("readiness", {}) + "rpc.exports={readiness:function(){return {javaAvailable:Java.available,platform:Process.platform,arch:Process.arch};}};\n"


def java_class_enumeration() -> str:
    return _header("java-class-discovery", {}) + "rpc.exports={enumerate:function(){if(!Java.available){return {error:'Java runtime is unavailable',items:[]};}var items=[];Java.perform(function(){Java.enumerateLoadedClassesSync().forEach(function(n){items.push({className:n});});});return {items:items};}};\n"


def java_member_enumeration(class_name: str, fields: bool = False) -> str:
    name = _json(class_name); kind = "java-field-discovery" if fields else "java-method-discovery"
    body = "var k=Java.use(NAME);var c=k.class;"
    if fields:
        body += "c.getDeclaredFields().forEach(function(f){items.push({fieldName:String(f.getName()),typeName:String(f.getType().getName()),visibility:String(f.getModifiers())});});"
    else:
        body += "Object.keys(k).forEach(function(n){try{if(k[n]&&k[n].overloads){k[n].overloads.forEach(function(o,i){items.push({methodName:n,overloadIndex:i,argumentTypes:o.argumentTypes.map(function(t){return t.className;}),returnType:o.returnType.className});});}}catch(e){}});"
    return _header(kind, {"class": class_name}) + f"var NAME={name};rpc.exports={{enumerate:function(){{if(!Java.available){{return {{error:'Java runtime is unavailable',items:[]}};}}var items=[];Java.perform(function(){{{body}}});return {{items:items}};}}}};\n"


def native_module_enumeration() -> str:
    return _header("native-module-discovery", {}) + "rpc.exports={enumerate:function(){return {items:Process.enumerateModules().map(function(m){return {moduleName:m.name,path:m.path,baseAddress:String(m.base),size:m.size};})};}};\n"


def native_export_enumeration(module_name: str) -> str:
    return _header("native-export-discovery", {"module": module_name}) + f"var NAME={_json(module_name)};rpc.exports={{enumerate:function(){{var m=Process.getModuleByName(NAME);return {{items:m.enumerateExports().map(function(e){{return {{symbolName:e.name,symbolType:e.type,address:String(e.address),moduleName:NAME}};}})}};}}}};\n"


def java_observation(metadata: dict[str, Any], class_name: str, method_name: str, overload: tuple[str, ...], options: dict[str, Any], modification: dict[str, Any]) -> str:
    values = {"metadata": metadata, "class": class_name, "method": method_name, "overload": list(overload), "options": options, "modification": modification}
    return _header("java-hook-state-changing" if modification else "java-hook-observation", metadata) + f"var CONFIG={_json(values)};var guard=false;var emitted=0;var windowStart=Date.now();function safe(v){{try{{var s=JSON.stringify(v);return s&&s.length>CONFIG.options.maxPreview?s.slice(0,CONFIG.options.maxPreview)+'…':v;}}catch(e){{return String(v);}}}}function emit(t,p){{var now=Date.now();if(now-windowStart>=1000){{windowStart=now;emitted=0;}}if(CONFIG.options.rateLimit&&emitted++>=CONFIG.options.rateLimit)return;send({{channel:'sus-adb-runtime',hookId:CONFIG.metadata.hookId,eventType:t,owner:CONFIG.class,member:CONFIG.method,payload:p}});}}if(Java.available){{Java.perform(function(){{var k=Java.use(CONFIG.class);var o=k[CONFIG.method].overload.apply(k[CONFIG.method],CONFIG.overload);var original=o; o.implementation=function(){{var args=Array.prototype.slice.call(arguments);if(guard){{return original.apply(this,args);}}guard=true;try{{if(CONFIG.options.logArguments)emit('method-enter',{{arguments:args.map(safe)}});if(CONFIG.modification.mode==='replace-argument')args[CONFIG.modification.argumentIndex]=CONFIG.modification.value;if(CONFIG.modification.mode==='throw-exception')throw Java.use(CONFIG.modification.exceptionClass).$new(CONFIG.modification.message);var result=original.apply(this,args);if(CONFIG.modification.mode==='replace-return')result=CONFIG.modification.value;if(CONFIG.options.logReturn)emit('method-leave',{{returnValue:safe(result)}});if(CONFIG.options.javaStack)emit('stack',{{stack:String(Java.use('android.util.Log').getStackTraceString(Java.use('java.lang.Exception').$new()))}});return result;}}catch(e){{if(CONFIG.options.logExceptions)emit('exception',{{exception:String(e),stack:e.stack||''}});throw e;}}finally{{guard=false;}}}};}});}}else{{emit('warning',{{message:'Java runtime is unavailable'}});}}\n"


def native_observation(metadata: dict[str, Any], module_name: str, symbol_name: str, options: dict[str, Any]) -> str:
    values = {"metadata": metadata, "module": module_name, "symbol": symbol_name, "options": options}
    return _header("native-hook-observation", metadata) + f"var CONFIG={_json(values)};var address=Module.getExportByName(CONFIG.module,CONFIG.symbol);var count=0;var windowStart=Date.now();function allowed(){{var now=Date.now();if(now-windowStart>=1000){{windowStart=now;count=0;}}return !CONFIG.options.rateLimit||count++<CONFIG.options.rateLimit;}}Interceptor.attach(address,{{onEnter:function(args){{this.susAdbAllowed=allowed();if(!this.susAdbAllowed)return;send({{channel:'sus-adb-runtime',hookId:CONFIG.metadata.hookId,eventType:'native-enter',owner:CONFIG.module,member:CONFIG.symbol,payload:{{arguments:CONFIG.options.logArguments?[String(args[0]),String(args[1]),String(args[2]),String(args[3])]:[]}}}});if(CONFIG.options.nativeBacktrace)send({{channel:'sus-adb-runtime',hookId:CONFIG.metadata.hookId,eventType:'stack',owner:CONFIG.module,member:CONFIG.symbol,payload:{{stack:Thread.backtrace(this.context,Backtracer.ACCURATE).map(DebugSymbol.fromAddress).join('\\n')}}}});}},onLeave:function(retval){{if(this.susAdbAllowed&&CONFIG.options.logReturn)send({{channel:'sus-adb-runtime',hookId:CONFIG.metadata.hookId,eventType:'native-leave',owner:CONFIG.module,member:CONFIG.symbol,payload:{{returnValue:String(retval)}}}});}}}});\n"
