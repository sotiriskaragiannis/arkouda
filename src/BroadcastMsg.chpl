module BroadcastMsg {
  use MultiTypeSymbolTable;
  use MultiTypeSymEntry;
  use ServerErrors;
  use Reflection;
  use Broadcast;
  use ServerConfig;
  use Logging;
  use Message;

  private config const logLevel = ServerConfig.logLevel;
  const bmLogger = new Logger(logLevel);

  /* 
   * Broadcast a value per segment of a segmented array to the
   * full size of the array, optionally applying a permutation
   * to return the result in the order of the original array.
   */
  proc broadcastMsg(cmd: string, payload: string, argSize: int, st: borrowed SymTab): MsgTuple throws {
    var msgArgs = parseMessageArgs(payload, argSize);
    const size = msgArgs.get("size").getIntValue();
    // Segments must be an int64 array
    const gs = getGenericTypedArrayEntry(msgArgs.getValueOf("segName"), st);
    if gs.dtype != DType.Int64 {
      throw new owned ErrorWithContext("Segments array must have dtype int64",
                                       getLineNumber(),
                                       getRoutineName(),
                                       getModuleName(),
                                       "TypeError");
    }
    const segs = toSymEntry(gs, int);
    // Check that values exists (can be any dtype)
    const gv = getGenericTypedArrayEntry(msgArgs.getValueOf("valName"), st);
    // Name of result array
    const rname = st.nextName();
    // This operation has two modes: one uses a permutation to reorder the answer,
    // while the other does not
    const usePerm: bool = msgArgs.get("permute").getBoolValue();
    if usePerm {
      // If using a permutation, the array must be int64 and same size as the size parameter
      const gp = getGenericTypedArrayEntry(msgArgs.getValueOf("permName"), st);
      if gp.dtype != DType.Int64 {
        throw new owned ErrorWithContext("Permutation array must have dtype int64",
                                         getLineNumber(),
                                         getRoutineName(),
                                         getModuleName(),
                                         "TypeError");
      }
      if gp.size != size {
        throw new owned ErrorWithContext("Requested result size must match permutation array size",
                                         getLineNumber(),
                                         getRoutineName(),
                                         getModuleName(),
                                         "ValueError");
      }
      const perm = toSymEntry(gp, int);
      // Select on dtype of values
      select gv.dtype {
        when DType.Int64 {
          const vals = toSymEntry(gv, int);
          var res = st.addEntry(rname, size, int);
          res.a = broadcast(perm.a, segs.a, vals.a);
        }
        when DType.UInt64 {
          const vals = toSymEntry(gv, uint);
          var res = st.addEntry(rname, size, uint);
          res.a = broadcast(perm.a, segs.a, vals.a);
        }
        when DType.Float64 {
          const vals = toSymEntry(gv, real);
          var res = st.addEntry(rname, size, real);
          res.a = broadcast(perm.a, segs.a, vals.a);
        }
        when DType.Bool {
          const vals = toSymEntry(gv, bool);
          var res = st.addEntry(rname, size, bool);
          res.a = broadcast(perm.a, segs.a, vals.a);
        }
        otherwise {
          throw new owned ErrorWithContext("Values array has unsupported dtype %s".format(gv.dtype:string),
                                           getLineNumber(),
                                           getRoutineName(),
                                           getModuleName(),
                                           "TypeError");
        }
      }
    } else {
      // If not using permutation, ignore perm array
      select gv.dtype {
        when DType.Int64 {
          const vals = toSymEntry(gv, int);
          var res = st.addEntry(rname, size, int);
          res.a = broadcast(segs.a, vals.a, size);
        }
        when DType.UInt64 {
          const vals = toSymEntry(gv, uint);
          var res = st.addEntry(rname, size, uint);
          res.a = broadcast(segs.a, vals.a, size);
        }
        when DType.Float64 {
          const vals = toSymEntry(gv, real);
          var res = st.addEntry(rname, size, real);
          res.a = broadcast(segs.a, vals.a, size);
        }
        when DType.Bool {
          const vals = toSymEntry(gv, bool);
          var res = st.addEntry(rname, size, bool);
          res.a = broadcast(segs.a, vals.a, size);
        }
        otherwise {
          throw new owned ErrorWithContext("Values array has unsupported dtype %s".format(gv.dtype:string),
                                           getLineNumber(),
                                           getRoutineName(),
                                           getModuleName(),
                                           "TypeError");
        }
      }
    }
    var repMsg = "created " + st.attrib(rname); 
    bmLogger.debug(getModuleName(),getRoutineName(),getLineNumber(),repMsg);
    return new MsgTuple(repMsg, MsgType.NORMAL);    
  }

  use CommandMap;
  registerFunction("broadcast", broadcastMsg, getModuleName());
}
