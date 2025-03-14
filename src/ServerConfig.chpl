/* arkouda server config param and config const */
module ServerConfig
{
    use ZMQ only;
    use HDF5.C_HDF5 only H5get_libversion;
    use SymArrayDmap only makeDistDom;

    public use IO;
    private use CTypes;

    use ServerErrorStrings;
    use Reflection;
    use ServerErrors;
    use Logging;
    
    enum Deployment {STANDARD,KUBERNETES}
    
    /*
    Type of deployment, which currently is either STANDARD, meaning
    that Arkouda is deployed bare-metal or within an HPC environment, 
    or on Kubernetes, defaults to Deployment.STANDARD
    */
    config const deployment = Deployment.STANDARD;

    /*
    Trace logging flag
    */
    config const trace = true;

    /*
    Global log level flag that defaults to LogLevel.INFO
    */
    config var logLevel = LogLevel.INFO;

    /*
    Port for zeromq
    */
    config const ServerPort = 5555;

    /*
    Memory usage limit -- percentage of physical memory
    */
    config const perLocaleMemLimit = 90;

    /*
    Bit width of digits for the LSD radix sort and related ops
     */
    config param RSLSD_bitsPerDigit = 16;
    
    /*
    Arkouda version
    */
    config param arkoudaVersion:string = "Please set during compilation";

    /*
    Write the server `hostname:port` to this file.
    */
    config const serverConnectionInfo: string = getEnv("ARKOUDA_SERVER_CONNECTION_INFO", "");

    /*
    Hostname where I am running
    */
    var serverHostname: string = try! get_hostname();

    proc get_hostname(): string {
      return here.hostname;
    }

    /*
     * Retrieves the hostname of the locale 0 arkouda_server process, which is useful for 
     * registering Arkouda with cloud environments such as Kubernetes.
     */
    proc getConnectHostname() throws {
        var hostname: string;
        on Locales[0] {
            hostname = here.name.strip('-0');
        }
        return hostname;
    }

    /*
     * Returns the version of Chapel arkouda was built with
     */
    proc getChplVersion() throws {
        use Version;
        // Prior to 1.28, chplVersion had a prepended version that has
        // since been removed
        return (chplVersion:string).replace('version ', '');
    }

    /*
    Indicates the version of Chapel Arkouda was built with
    */
    const chplVersion = try! getChplVersion();

    /*
    Indicates whether token authentication is being used for Akrouda server requests
    */
    config const authenticate : bool = false;

    /*
    Determines the maximum number of capture groups returned by Regex.matches
    */
    config param regexMaxCaptures = 20;

    config const saveUsedModules : bool = false;

    private config const lLevel = ServerConfig.logLevel;
    const scLogger = new Logger(lLevel);
   
    proc createConfig() {
        use CTypes;

        class LocaleConfig {
            const id: int;
            const name: string;
            const numPUs: int;
            const maxTaskPar: int;
            const physicalMemory: int;

            proc init(id: int) {
                on Locales[id] {
                    this.id = here.id;
                    this.name = here.name;
                    this.numPUs = here.numPUs();
                    this.maxTaskPar = here.maxTaskPar;
                    this.physicalMemory = getPhysicalMemHere();
                }
            }
        }

        class Config {
            const arkoudaVersion: string;
            const chplVersion: string;
            const ZMQVersion: string;
            const HDF5Version: string;
            const serverHostname: string;
            const ServerPort: int;
            const numLocales: int;
            const numPUs: int;
            const maxTaskPar: int;
            const physicalMemory: int;
            const distributionType: string;
            const LocaleConfigs: [LocaleSpace] owned LocaleConfig;
            const authenticate: bool;
            const logLevel: LogLevel;
            const regexMaxCaptures: int;
            const byteorder: string;
        }

        var (Zmajor, Zminor, Zmicro) = ZMQ.version;
        var H5major: c_uint, H5minor: c_uint, H5micro: c_uint;
        H5get_libversion(H5major, H5minor, H5micro);
        
        const cfg = new owned Config(
            arkoudaVersion = (ServerConfig.arkoudaVersion:string),
            chplVersion = chplVersion,
            ZMQVersion = try! "%i.%i.%i".format(Zmajor, Zminor, Zmicro),
            HDF5Version = try! "%i.%i.%i".format(H5major, H5minor, H5micro),
            serverHostname = serverHostname,
            ServerPort = ServerPort,
            numLocales = numLocales,
            numPUs = here.numPUs(),
            maxTaskPar = here.maxTaskPar,
            physicalMemory = getPhysicalMemHere(),
            distributionType = (makeDistDom(10).type):string,
            LocaleConfigs = [loc in LocaleSpace] new owned LocaleConfig(loc),
            authenticate = authenticate,
            logLevel = logLevel,
            regexMaxCaptures = regexMaxCaptures,
            byteorder = try! getByteorder()
        );
        return try! "%jt".format(cfg);

    }
    private var cfgStr = createConfig();

    proc getConfig(): string {
        return cfgStr;
    }

    proc getEnv(name: string, default=""): string {
        extern proc getenv(name : c_string) : c_string;
        var val = getenv(name.localize().c_str()): string;
        if val.isEmpty() { val = default; }
        return val;
    }

    /*
    Get the physical memory available on this locale
    */ 
    proc getPhysicalMemHere() {
        use Memory.Diagnostics;
        return here.physicalMemory();
    }

    /*
    Get the byteorder (endianness) of this locale
    */
    proc getByteorder() throws {
        use IO;
        var writeVal = 1, readVal = 0;
        var tmpf = openmem();
        tmpf.writer(kind=iobig).write(writeVal);
        tmpf.reader(kind=ionative).read(readVal);
        return if writeVal == readVal then "big" else "little";
    }

    /*
    Get the memory used on this locale
    */
    proc getMemUsed() {
        use Memory.Diagnostics;
        return memoryUsed();
    }

    /*
    Get the memory limit for this server run
    returns a percentage of the physical memory per locale
    */
    proc getMemLimit():uint {
        return ((perLocaleMemLimit:real / 100.0) * getPhysicalMemHere()):uint; // checks on locale-0
    }

    var memHighWater:uint = 0;
    
    /*
    check used + amount is over the memory limit
    throw error if we would go over the limit
    */
    proc overMemLimit(additionalAmount:int) throws {
        // must set config var "-smemTrack=true"(compile time) or "--memTrack=true" (run time)
        // to use memoryUsed() procedure from Chapel's Memory module
        if (memTrack) {
            // this is a per locale total
            var total = getMemUsed() + (additionalAmount:uint / numLocales:uint);
            if (trace) {
                if (total > memHighWater) {
                    memHighWater = total;
                    scLogger.info(getModuleName(),getRoutineName(),getLineNumber(),
                    "memory high watermark = %i memory limit = %i".format(
                           memHighWater:uint * numLocales:uint, 
                           getMemLimit():uint * numLocales:uint));
                }
            }
            if total > getMemLimit() {
                var msg = "Error: Operation would exceed memory limit ("
                                             +total:string+","+getMemLimit():string+")";
                scLogger.error(getModuleName(),getRoutineName(),getLineNumber(), msg);  
                throw getErrorWithContext(
                          msg=msg,
                          lineNumber=getLineNumber(),
                          routineName=getRoutineName(),
                          moduleName=getModuleName(),
                          errorClass="ErrorWithContext");                                        
            }
        }
    }

    proc string.splitMsgToTuple(param numChunks: int) {
      var tup: numChunks*string;
      var count = tup.indices.low;

      // fill in the initial tuple elements defined by split()
      for s in this.split(numChunks-1) {
        tup(count) = s;
        count += 1;
      }
      // if split() had fewer items than the tuple, fill in the rest
      if (count < numChunks) {
        for i in count..numChunks-1 {
          tup(i) = "";
        }
      }
      return tup;
    }

    proc string.splitMsgToTuple(sep: string, param numChunks: int) {
      var tup: numChunks*string;
      var count = tup.indices.low;

      // fill in the initial tuple elements defined by split()
      for s in this.split(sep, numChunks-1) {
        tup(count) = s;
        count += 1;
      }
      // if split() had fewer items than the tuple, fill in the rest
      if (count < numChunks) {
        for i in count..numChunks-1 {
          tup(i) = "";
        }
      }
      return tup;
    }

    proc bytes.splitMsgToTuple(param numChunks: int) {
      var tup: numChunks*bytes;
      var count = tup.indices.low;

      // fill in the initial tuple elements defined by split()
      for s in this.split(numChunks-1) {
        tup(count) = s;
        count += 1;
      }
      // if split() had fewer items than the tuple, fill in the rest
      if (count < numChunks) {
        for i in count..numChunks-1 {
          tup(i) = b"";
        }
      }
      return tup;
    }

    proc bytes.splitMsgToTuple(sep: bytes, param numChunks: int) {
      var tup: numChunks*bytes;
      var count = tup.indices.low;

      // fill in the initial tuple elements defined by split()
      for s in this.split(sep, numChunks-1) {
        tup(count) = s;
        count += 1;
      }
      // if split() had fewer items than the tuple, fill in the rest
      if (count < numChunks) {
        for i in count..numChunks-1 {
          tup(i) = b"";
        }
      }
      return tup;
    }

    proc getEnvInt(name: string, default: int): int {
      extern proc getenv(name : c_string) : c_string;
      var strval = getenv(name.localize().c_str()): string;
      if strval.isEmpty() { return default; }
      return try! strval: int;
    }

    /*
     * String constants for use in constructing JSON formatted messages
     */
    const Q = '"'; // Double Quote, escaping quotes often throws off syntax highlighting.
    const QCQ = Q + ":" + Q; // `":"` -> useful for closing and opening quotes for named json k,v pairs
    const BSLASH = '\\';
    const ESCAPED_QUOTES = BSLASH + Q;

    proc appendToConfigStr(key:string, val:string) {
      var idx_close = cfgStr.rfind("}"):int;
      var tmp_json = cfgStr(0..idx_close-1);
      cfgStr = tmp_json + "," + Q + key + QCQ + val + Q + "}";
    }
}
