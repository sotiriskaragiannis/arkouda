/* Array set operations
 includes intersection, union, xor, and diff

 currently, only performs operations with integer arrays 
 */

module ArraySetopsMsg
{
    use ServerConfig;

    use Time only;
    use Math only;
    use Reflection only;

    use MultiTypeSymbolTable;
    use MultiTypeSymEntry;
    use SegmentedString;
    use ServerErrorStrings;

    use ArraySetops;
    use Indexing;
    use RadixSortLSD;
    use Reflection;
    use ServerErrors;
    use Logging;
    use Message;

    private config const logLevel = ServerConfig.logLevel;
    const asLogger = new Logger(logLevel);
    
    /*
    Parse, execute, and respond to a intersect1d message
    :arg reqMsg: request containing (cmd,name,name2,assume_unique)
    :type reqMsg: string
    :arg st: SymTab to act on
    :type st: borrowed SymTab
    :returns: (MsgTuple) response message
    */
    proc intersect1dMsg(cmd: string, payload: string, argSize: int, st: borrowed SymTab): MsgTuple throws {
        param pn = Reflection.getRoutineName();
        var repMsg: string; // response message
        var msgArgs = parseMessageArgs(payload, argSize);
        var isUnique = msgArgs.get("assume_unique").getBoolValue();
        
        var vname = st.nextName();

        var gEnt: borrowed GenSymEntry = getGenericTypedArrayEntry(msgArgs.getValueOf("arg1"), st);
        var gEnt2: borrowed GenSymEntry = getGenericTypedArrayEntry(msgArgs.getValueOf("arg2"), st);
        
        var gEnt_sortMem = radixSortLSD_memEst(gEnt.size, gEnt.itemsize);
        var gEnt2_sortMem = radixSortLSD_memEst(gEnt2.size, gEnt2.itemsize);
        var intersect_maxMem = max(gEnt_sortMem, gEnt2_sortMem);
        overMemLimit(intersect_maxMem);

        select(gEnt.dtype, gEnt2.dtype) {
          when (DType.Int64, DType.Int64) {
            var e = toSymEntry(gEnt,int);
            var f = toSymEntry(gEnt2,int);

            var aV = intersect1d(e.a, f.a, isUnique);
            st.addEntry(vname, new shared SymEntry(aV));

            repMsg = "created " + st.attrib(vname);
            asLogger.debug(getModuleName(),getRoutineName(),getLineNumber(),repMsg);
            return new MsgTuple(repMsg, MsgType.NORMAL);
          }
          when (DType.UInt64, DType.UInt64) {
            var e = toSymEntry(gEnt,uint);
            var f = toSymEntry(gEnt2,uint);

            var aV = intersect1d(e.a, f.a, isUnique);
            st.addEntry(vname, new shared SymEntry(aV));

            repMsg = "created " + st.attrib(vname);
            asLogger.debug(getModuleName(),getRoutineName(),getLineNumber(),repMsg);
            return new MsgTuple(repMsg, MsgType.NORMAL);
          }
          otherwise {
            var errorMsg = notImplementedError("intersect1d",gEnt.dtype);
            asLogger.error(getModuleName(),getRoutineName(),getLineNumber(),errorMsg);           
            return new MsgTuple(errorMsg, MsgType.ERROR);
          }
        }
    }

    /*
    Parse, execute, and respond to a setxor1d message
    :arg reqMsg: request containing (cmd,name,name2,assume_unique)
    :type reqMsg: string
    :arg st: SymTab to act on
    :type st: borrowed SymTab
    :returns: (MsgTuple) response message
    */
    proc setxor1dMsg(cmd: string, payload: string, argSize: int, st: borrowed SymTab): MsgTuple throws {
        param pn = Reflection.getRoutineName();
        var repMsg: string; // response message
        var msgArgs = parseMessageArgs(payload, argSize);
        var isUnique = msgArgs.get("assume_unique").getBoolValue();

        var vname = st.nextName();

        var gEnt: borrowed GenSymEntry = getGenericTypedArrayEntry(msgArgs.getValueOf("arg1"), st);
        var gEnt2: borrowed GenSymEntry = getGenericTypedArrayEntry(msgArgs.getValueOf("arg2"), st);

        var gEnt_sortMem = radixSortLSD_memEst(gEnt.size, gEnt.itemsize);
        var gEnt2_sortMem = radixSortLSD_memEst(gEnt2.size, gEnt2.itemsize);
        var xor_maxMem = max(gEnt_sortMem, gEnt2_sortMem);
        overMemLimit(xor_maxMem);

        select(gEnt.dtype, gEnt2.dtype) {
          when (DType.Int64, DType.Int64) {
             var e = toSymEntry(gEnt,int);
             var f = toSymEntry(gEnt2,int);
             
             var aV = setxor1d(e.a, f.a, isUnique);
             st.addEntry(vname, new shared SymEntry(aV));

             repMsg = "created " + st.attrib(vname);
             asLogger.debug(getModuleName(),getRoutineName(),getLineNumber(),repMsg);
             return new MsgTuple(repMsg, MsgType.NORMAL);
           }
           when (DType.UInt64, DType.UInt64) {
             var e = toSymEntry(gEnt,uint);
             var f = toSymEntry(gEnt2,uint);
             
             var aV = setxor1d(e.a, f.a, isUnique);
             st.addEntry(vname, new shared SymEntry(aV));

             repMsg = "created " + st.attrib(vname);
             asLogger.debug(getModuleName(),getRoutineName(),getLineNumber(),repMsg);
             return new MsgTuple(repMsg, MsgType.NORMAL);
           }
           otherwise {
               var errorMsg = notImplementedError("setxor1d",gEnt.dtype);
               asLogger.error(getModuleName(),getRoutineName(),getLineNumber(),errorMsg);                  
               return new MsgTuple(errorMsg, MsgType.ERROR);
           }
        }
    }

    /*
    Parse, execute, and respond to a setdiff1d message
    :arg reqMsg: request containing (cmd,name,name2,assume_unique)
    :type reqMsg: string
    :arg st: SymTab to act on
    :type st: borrowed SymTab
    :returns: (MsgTuple) response message
    */
    proc setdiff1dMsg(cmd: string, payload: string, argSize: int, st: borrowed SymTab): MsgTuple throws {
        param pn = Reflection.getRoutineName();
        var repMsg: string; // response message
        var msgArgs = parseMessageArgs(payload, argSize);
        var isUnique = msgArgs.get("assume_unique").getBoolValue();

        var vname = st.nextName();

        var gEnt: borrowed GenSymEntry = getGenericTypedArrayEntry(msgArgs.getValueOf("arg1"), st);
        var gEnt2: borrowed GenSymEntry = getGenericTypedArrayEntry(msgArgs.getValueOf("arg2"), st);

        var gEnt_sortMem = radixSortLSD_memEst(gEnt.size, gEnt.itemsize);
        var gEnt2_sortMem = radixSortLSD_memEst(gEnt2.size, gEnt2.itemsize);
        var diff_maxMem = max(gEnt_sortMem, gEnt2_sortMem);
        overMemLimit(diff_maxMem);

        select(gEnt.dtype, gEnt2.dtype) {
          when (DType.Int64, DType.Int64) {
             var e = toSymEntry(gEnt,int);
             var f = toSymEntry(gEnt2, int);
             
             var aV = setdiff1d(e.a, f.a, isUnique);
             st.addEntry(vname, new shared SymEntry(aV));

             var repMsg = "created " + st.attrib(vname);
             asLogger.debug(getModuleName(),getRoutineName(),getLineNumber(),repMsg);
             return new MsgTuple(repMsg, MsgType.NORMAL);
           }
           when (DType.UInt64, DType.UInt64) {
             var e = toSymEntry(gEnt,uint);
             var f = toSymEntry(gEnt2, uint);
             
             var aV = setdiff1d(e.a, f.a, isUnique);
             st.addEntry(vname, new shared SymEntry(aV));

             var repMsg = "created " + st.attrib(vname);
             asLogger.debug(getModuleName(),getRoutineName(),getLineNumber(),repMsg);
             return new MsgTuple(repMsg, MsgType.NORMAL);
           }
           otherwise {
               var errorMsg = notImplementedError("setdiff1d",gEnt.dtype);
               asLogger.error(getModuleName(),getRoutineName(),getLineNumber(),errorMsg);                 
               return new MsgTuple(errorMsg, MsgType.ERROR);           
           }
        }
    }

    /*
    Parse, execute, and respond to a union1d message
    :arg reqMsg: request containing (cmd,name,name2,assume_unique)
    :type reqMsg: string
    :arg st: SymTab to act on
    :type st: borrowed SymTab
    :returns: (MsgTuple) response message
    */
    proc union1dMsg(cmd: string, payload: string, argSize: int, st: borrowed SymTab): MsgTuple throws {
      param pn = Reflection.getRoutineName();
      var repMsg: string; // response message
      var msgArgs = parseMessageArgs(payload, argSize);

      var vname = st.nextName();

      var gEnt: borrowed GenSymEntry = getGenericTypedArrayEntry(msgArgs.getValueOf("arg1"), st);
      var gEnt2: borrowed GenSymEntry = getGenericTypedArrayEntry(msgArgs.getValueOf("arg2"), st);
      
      var gEnt_sortMem = radixSortLSD_memEst(gEnt.size, gEnt.itemsize);
      var gEnt2_sortMem = radixSortLSD_memEst(gEnt2.size, gEnt2.itemsize);
      var union_maxMem = max(gEnt_sortMem, gEnt2_sortMem);
      overMemLimit(union_maxMem);

      select(gEnt.dtype, gEnt2.dtype) {
        when (DType.Int64, DType.Int64) {
           var e = toSymEntry(gEnt,int);
           var f = toSymEntry(gEnt2,int);

           var aV = union1d(e.a, f.a);
           st.addEntry(vname, new shared SymEntry(aV));

           var repMsg = "created " + st.attrib(vname);
           asLogger.debug(getModuleName(),getRoutineName(),getLineNumber(),repMsg);
           return new MsgTuple(repMsg, MsgType.NORMAL);
         }
         when (DType.UInt64, DType.UInt64) {
           var e = toSymEntry(gEnt,uint);
           var f = toSymEntry(gEnt2,uint);

           var aV = union1d(e.a, f.a);
           st.addEntry(vname, new shared SymEntry(aV));

           var repMsg = "created " + st.attrib(vname);
           asLogger.debug(getModuleName(),getRoutineName(),getLineNumber(),repMsg);
           return new MsgTuple(repMsg, MsgType.NORMAL);
         }
         otherwise {
             var errorMsg = notImplementedError("newUnion1d",gEnt.dtype);
             asLogger.error(getModuleName(),getRoutineName(),getLineNumber(),errorMsg);                   
             return new MsgTuple(errorMsg, MsgType.ERROR);              
         }
      }
    }

    proc stringtobool(str: string): bool throws {
        if str == "True" then return true;
        else if str == "False" then return false;
        throw getErrorWithContext(
            msg="message: assume_unique must be of type bool",
            lineNumber=getLineNumber(),
            routineName=getRoutineName(),
            moduleName=getModuleName(),
            errorClass="ErrorWithContext");
    }
    
    use CommandMap;
    registerFunction("intersect1d", intersect1dMsg, getModuleName());
    registerFunction("setdiff1d", setdiff1dMsg, getModuleName());
    registerFunction("setxor1d", setxor1dMsg, getModuleName());
    registerFunction("union1d", union1dMsg, getModuleName());
}
