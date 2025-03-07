
module In1dMsg
{
    use ServerConfig;

    use Reflection;
    use ServerErrors;
    use Logging;
    use Message;
    
    use MultiTypeSymbolTable;
    use MultiTypeSymEntry;
    use ServerErrorStrings;

    use In1d;

    private config const logLevel = ServerConfig.logLevel;
    const iLogger = new Logger(logLevel);
    
    /* in1d takes two pdarray and returns a bool pdarray
       with the "in"/contains for each element tested against the second pdarray.
       
       in1dMsg processes the request, considers the size of the arguements, and decides 
       which implementation
       of in1d to utilize.
    */
    proc in1dMsg(cmd: string, payload: string, argSize: int, st: borrowed SymTab): MsgTuple throws {
        param pn = Reflection.getRoutineName();
        var repMsg: string; // response message
        var msgArgs = parseMessageArgs(payload, argSize);
        var invert: bool = msgArgs.get("invert").getBoolValue();

        // get next symbol name
        var rname = st.nextName();

        const name: string = msgArgs.getValueOf("pda1");
        const sname: string = msgArgs.getValueOf("pda2");

        var gAr1: borrowed GenSymEntry = getGenericTypedArrayEntry(name, st);
        var gAr2: borrowed GenSymEntry = getGenericTypedArrayEntry(sname, st);
        
        iLogger.debug(getModuleName(),getRoutineName(),getLineNumber(),
                        "cmd: %s pdarray1: %s pdarray2: %s invert: %t new pdarray name: %t".format(
                                   cmd,st.attrib(name),st.attrib(sname),invert,rname));

        select (gAr1.dtype, gAr2.dtype) {
            when (DType.Int64, DType.Int64) {
                var ar1 = toSymEntry(gAr1,int);
                var ar2 = toSymEntry(gAr2,int);

                var truth = in1d(ar1.a, ar2.a, invert);
                st.addEntry(rname, new shared SymEntry(truth));
            }
            when (DType.UInt64, DType.UInt64) {
                var ar1 = toSymEntry(gAr1,uint);
                var ar2 = toSymEntry(gAr2,uint);

                var truth = in1d(ar1.a, ar2.a, invert);
                st.addEntry(rname, new shared SymEntry(truth));
            }
            otherwise {
                var errorMsg = notImplementedError(pn,gAr1.dtype,"in",gAr2.dtype);
                iLogger.error(getModuleName(),getRoutineName(),getLineNumber(),errorMsg);
                return new MsgTuple(errorMsg, MsgType.ERROR);
            }
        }
        repMsg = "created " + st.attrib(rname);
        iLogger.debug(getModuleName(),getRoutineName(),getLineNumber(),repMsg);
        return new MsgTuple(repMsg, MsgType.NORMAL);
    }

    use CommandMap;
    registerFunction("in1d", in1dMsg, getModuleName());
}
