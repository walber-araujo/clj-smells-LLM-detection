import os

base_path = "/Users/walber.filho.nufuturo/clj-smells-dataset/smells/environment_and_idioms/"

smells = {
    "unmanaged_resource_io": {
        "metadata": {
            "name": "Unmanaged Resource IO",
            "loc": "Function `process-file`, `write-log`, `handle-socket`",
            "forms": "`io/reader`, `io/writer`, `java.net.Socket.`",
            "expl_bad": "Failing to wrap I/O resources in `with-open` can lead to resource leaks if an exception is thrown or if they are not manually closed.",
            "expl_good": "Wrapping I/O resources in `with-open` ensures they are closed automatically, even if an exception occurs."
        },
        "bads": [
"""```Clojure
(ns data-pipeline.csv-processor
  (:require [clojure.java.io :as io]
            [clojure.data.csv :as csv]))

(defn process-csv [file-path]
  ; VALIDATION: SMELL START - Unmanaged Resource IO
  ; VALIDATION: io/reader opened without with-open, leading to potential resource leaks
  (let [reader (io/reader file-path)
        data (csv/read-csv reader)]
    (doall (map #(assoc % :processed true) data))))
  ; VALIDATION: SMELL END
```""",
"""```Clojure
(ns web-app.logger
  (:require [clojure.java.io :as io]))

(defn append-to-log [msg file-path]
  ; VALIDATION: SMELL START - Unmanaged Resource IO
  ; VALIDATION: io/writer opened without with-open
  (let [writer (io/writer file-path :append true)]
    (.write writer (str msg "\\n"))
    (.flush writer)))
  ; VALIDATION: SMELL END
```""",
"""```Clojure
(ns network.client
  (:import [java.net Socket]
           [java.io InputStreamReader BufferedReader]))

(defn fetch-status [host port]
  ; VALIDATION: SMELL START - Unmanaged Resource IO
  ; VALIDATION: Socket opened without with-open
  (let [socket (Socket. host port)
        in (BufferedReader. (InputStreamReader. (.getInputStream socket)))
        response (.readLine in)]
    response))
  ; VALIDATION: SMELL END
```"""
        ],
        "goods": [
"""```Clojure
(ns data-pipeline.csv-processor
  (:require [clojure.java.io :as io]
            [clojure.data.csv :as csv]))

(defn process-csv [file-path]
  (with-open [reader (io/reader file-path)]
    (let [data (csv/read-csv reader)]
      (doall (map #(assoc % :processed true) data)))))
```""",
"""```Clojure
(ns web-app.logger
  (:require [clojure.java.io :as io]))

(defn append-to-log [msg file-path]
  (with-open [writer (io/writer file-path :append true)]
    (.write writer (str msg "\\n"))
    (.flush writer)))
```"""
        ]
    },
    "relying_on_load_time_side_effects": {
        "metadata": {
            "name": "Relying on Load-Time Side Effects",
            "loc": "Top-level form",
            "forms": "`def`",
            "expl_bad": "Evaluating side-effectful code (like network requests or DB connections) at load time makes the namespace hard to test, reload, or use in other contexts.",
        },
        "bads": [
"""```Clojure
(ns app.db-init
  (:require [next.jdbc :as jdbc]))

; VALIDATION: SMELL START - Relying on Load-Time Side Effects
; VALIDATION: Establishing DB connection at load time
(def db-conn 
  (jdbc/get-connection {:dbtype "postgres" :dbname "prod"}))
; VALIDATION: SMELL END

(defn get-users []
  (jdbc/execute! db-conn ["SELECT * FROM users"]))
```""",
"""```Clojure
(ns app.config
  (:require [clojure.java.shell :as shell]))

; VALIDATION: SMELL START - Relying on Load-Time Side Effects
; VALIDATION: Reading environment variables and executing shell commands at load time
(def api-key
  (or (System/getenv "API_KEY")
      (:out (shell/sh "cat" "/secrets/api_key.txt"))))
; VALIDATION: SMELL END
```""",
"""```Clojure
(ns app.remote-config
  (:require [clj-http.client :as http]))

; VALIDATION: SMELL START - Relying on Load-Time Side Effects
; VALIDATION: Making an HTTP request at load time
(def remote-settings
  (:body (http/get "https://config.server/api/settings" {:as :json})))
; VALIDATION: SMELL END
```""",
"""```Clojure
(ns app.file-cache
  (:require [clojure.edn :as edn]))

; VALIDATION: SMELL START - Relying on Load-Time Side Effects
; VALIDATION: Reading a file into memory at load time
(def cached-data
  (edn/read-string (slurp "data/cache.edn")))
; VALIDATION: SMELL END
```""",
"""```Clojure
(ns app.auth
  (:require [clj-http.client :as http]))

; VALIDATION: SMELL START - Relying on Load-Time Side Effects
; VALIDATION: Fetching a token from an external service during namespace load
(def auth-token
  (-> (http/post "https://auth.provider/token" 
                 {:form-params {:client_id "my-app" :secret "my-secret"} :as :json})
      :body :access_token))
; VALIDATION: SMELL END
```"""
        ],
        "goods": []
    },
    "namespace_load_side_effects": {
        "metadata": {
            "name": "Namespace Load Side Effects",
            "loc": "Top-level form",
            "forms": "`require`, `requiring-resolve`",
            "expl_bad": "Using `require` as a top-level form outside the `ns` declaration breaks standard dependency tooling and makes the code harder to reason about.",
            "expl_good": "Dependencies should be explicitly declared within the `ns` form using `:require`."
        },
        "bads": [
"""```Clojure
(ns reporting.core)

; VALIDATION: SMELL START - Namespace Load Side Effects
; VALIDATION: Calling require outside the ns form
(require '[clojure.string :as str])
; VALIDATION: SMELL END

(defn generate-report [data]
  (str/join "," data))
```""",
"""```Clojure
(ns app.plugins.loader)

; VALIDATION: SMELL START - Namespace Load Side Effects
; VALIDATION: requiring-resolve used at the top-level
(def plugin-init 
  (requiring-resolve 'app.plugins.custom/init))
; VALIDATION: SMELL END

(defn start-plugin []
  (plugin-init))
```""",
"""```Clojure
(ns utils.math)

; VALIDATION: SMELL START - Namespace Load Side Effects
; VALIDATION: Top-level require for optional dependency
(try
  (require '[fast-math.core :as math])
  (catch Exception _
    (println "Fast math not found, using slow math")))
; VALIDATION: SMELL END
```"""
        ],
        "goods": [
"""```Clojure
(ns reporting.core
  (:require [clojure.string :as str]))

(defn generate-report [data]
  (str/join "," data))
```""",
"""```Clojure
(ns app.plugins.loader)

(defn start-plugin []
  (let [plugin-init (requiring-resolve 'app.plugins.custom/init)]
    (plugin-init)))
```"""
        ]
    },
    "multiple_evaluation_in_macros": {
        "metadata": {
            "name": "Multiple Evaluation in Macros",
            "loc": "Macro `unless`, `time-it`",
            "forms": "`defmacro`",
            "expl_bad": "A macro that evaluates an argument more than once can cause unexpected side effects or performance issues if the argument expression does work.",
            "expl_good": "Macros should evaluate their arguments once by binding them to a gensym in a `let` block."
        },
        "bads": [
"""```Clojure
(ns utils.control
  (:require [clojure.tools.logging :as log]))

(defmacro unless [pred a b]
  ; VALIDATION: SMELL START - Multiple Evaluation in Macros
  ; VALIDATION: 'pred' is evaluated twice if it is false
  `(if (not ~pred)
     (do
       (log/info "Pred was false:" '~pred)
       ~b)
     ~a))
  ; VALIDATION: SMELL END
```""",
"""```Clojure
(ns utils.bench)

(defmacro time-it [expr]
  ; VALIDATION: SMELL START - Multiple Evaluation in Macros
  ; VALIDATION: 'expr' is evaluated twice: once to check result, once to return
  `(let [start# (System/nanoTime)
         res# ~expr
         end# (System/nanoTime)]
     (println "Time taken:" (- end# start#))
     (if res#
       ~expr
       nil)))
  ; VALIDATION: SMELL END
```""",
"""```Clojure
(ns utils.assert)

(defmacro assert-pos [n]
  ; VALIDATION: SMELL START - Multiple Evaluation in Macros
  ; VALIDATION: 'n' is evaluated multiple times
  `(if (> ~n 0)
     ~n
     (throw (ex-info "Not positive" {:val ~n}))))
  ; VALIDATION: SMELL END
```"""
        ],
        "goods": [
"""```Clojure
(ns utils.control
  (:require [clojure.tools.logging :as log]))

(defmacro unless [pred a b]
  `(let [p# ~pred]
     (if (not p#)
       (do
         (log/info "Pred was false:" '~pred)
         ~b)
       ~a)))
```""",
"""```Clojure
(ns utils.bench)

(defmacro time-it [expr]
  `(let [start# (System/nanoTime)
         res# ~expr
         end# (System/nanoTime)]
     (println "Time taken:" (- end# start#))
     res#))
```"""
        ]
    },
    "direct_usage_of_clojure_lang_rt": {
        "metadata": {
            "name": "Direct Usage of clojure.lang.RT",
            "loc": "Function `process`, `get-count`",
            "forms": "`clojure.lang.RT/iter`, `clojure.lang.RT/count`",
            "expl_bad": "Calling methods on `clojure.lang.RT` directly bypasses the public Clojure API, tightly coupling the code to internal implementation details.",
            "expl_good": "Use the standard Clojure functions like `iterator-seq` or `count` instead of internal Java methods."
        },
        "bads": [
"""```Clojure
(ns interop.java
  (:import [java.util ArrayList]))

(defn process-list [^ArrayList arr-list]
  ; VALIDATION: SMELL START - Direct Usage of clojure.lang.RT
  ; VALIDATION: Using RT/iter instead of iterator-seq
  (let [iter (clojure.lang.RT/iter arr-list)]
    (while (.hasNext iter)
      (println (.next iter)))))
  ; VALIDATION: SMELL END
```""",
"""```Clojure
(ns data.utils)

(defn get-item-count [coll]
  ; VALIDATION: SMELL START - Direct Usage of clojure.lang.RT
  ; VALIDATION: Using RT/count directly instead of clojure.core/count
  (clojure.lang.RT/count coll))
  ; VALIDATION: SMELL END
```""",
"""```Clojure
(ns utils.seq)

(defn force-seq [obj]
  ; VALIDATION: SMELL START - Direct Usage of clojure.lang.RT
  ; VALIDATION: Using RT/seq directly instead of clojure.core/seq
  (clojure.lang.RT/seq obj))
  ; VALIDATION: SMELL END
```"""
        ],
        "goods": [
"""```Clojure
(ns interop.java
  (:import [java.util ArrayList]))

(defn process-list [^ArrayList arr-list]
  (doseq [item (iterator-seq (.iterator arr-list))]
    (println item)))
```""",
"""```Clojure
(ns data.utils)

(defn get-item-count [coll]
  (count coll))
```"""
        ]
    },
    "unnecessary_macros": {
        "metadata": {
            "name": "Unnecessary Macros",
            "loc": "Macro `log-info`, `validate`",
            "forms": "`defmacro`",
            "expl_bad": "Using a macro when a function would suffice makes the code harder to compose, test, and apply to sequences.",
            "expl_good": "Use a function instead of a macro when you don't need to control evaluation order or manipulate syntax."
        },
        "bads": [
"""```Clojure
(ns logging.core)

; VALIDATION: SMELL START - Unnecessary Macros
; VALIDATION: This macro does not need to control evaluation and can just be a function
(defmacro log-info [msg]
  `(println "[INFO]" ~msg))
; VALIDATION: SMELL END

(defn process []
  (log-info "Starting process"))
```""",
"""```Clojure
(ns validation.core)

; VALIDATION: SMELL START - Unnecessary Macros
; VALIDATION: Simple validation wrapper does not require a macro
(defmacro valid-age? [age]
  `(and (>= ~age 0) (<= ~age 120)))
; VALIDATION: SMELL END
```""",
"""```Clojure
(ns math.utils)

; VALIDATION: SMELL START - Unnecessary Macros
; VALIDATION: Macro used for a simple arithmetic wrapper
(defmacro add-ten [x]
  `(+ ~x 10))
; VALIDATION: SMELL END
```"""
        ],
        "goods": [
"""```Clojure
(ns logging.core)

(defn log-info [msg]
  (println "[INFO]" msg))

(defn process []
  (log-info "Starting process"))
```""",
"""```Clojure
(ns validation.core)

(defn valid-age? [age]
  (and (>= age 0) (<= age 120)))
```"""
        ]
    },
    "production_doall": {
        "metadata": {
            "name": "Production doall",
            "loc": "Function `notify-users`, `save-records`",
            "forms": "`doall`",
            "expl_bad": "Using `doall` with `map` just to force side effects is non-idiomatic and creates an unnecessary intermediate sequence in memory.",
            "expl_good": "Use `run!` or `doseq` to perform side effects over a sequence without retaining the results."
        },
        "bads": [
"""```Clojure
(ns app.notifications
  (:require [app.email :as email]))

(defn notify-users [users]
  ; VALIDATION: SMELL START - Production doall
  ; VALIDATION: doall used purely for side-effects instead of run! or doseq
  (doall (map email/send-welcome! users)))
  ; VALIDATION: SMELL END
```""",
"""```Clojure
(ns app.db
  (:require [next.jdbc :as jdbc]))

(defn save-records [tx records]
  ; VALIDATION: SMELL START - Production doall
  ; VALIDATION: doall wrapping map for side effects
  (doall (map #(jdbc/execute! tx ["INSERT INTO tbl (data) VALUES (?)" %]) records)))
  ; VALIDATION: SMELL END
```""",
"""```Clojure
(ns app.sync
  (:require [clj-http.client :as http]))

(defn sync-files [urls]
  ; VALIDATION: SMELL START - Production doall
  ; VALIDATION: doall to force http calls
  (doall (map #(http/post %) urls)))
  ; VALIDATION: SMELL END
```"""
        ],
        "goods": [
"""```Clojure
(ns app.notifications
  (:require [app.email :as email]))

(defn notify-users [users]
  (run! email/send-welcome! users))
```""",
"""```Clojure
(ns app.db
  (:require [next.jdbc :as jdbc]))

(defn save-records [tx records]
  (doseq [record records]
    (jdbc/execute! tx ["INSERT INTO tbl (data) VALUES (?)" record])))
```"""
        ]
    },
    "misuse_of_channel_closing_semantics": {
        "metadata": {
            "name": "Misuse of Channel Closing Semantics",
            "loc": "Function `worker`",
            "forms": "`>!`, `put!`",
            "expl_bad": "Using a special sentinel value to signal the end of a core.async channel is unidiomatic; you should use `close!` instead.",
        },
        "bads": [
"""```Clojure
(ns async.worker
  (:require [clojure.core.async :as a]))

(defn process-jobs [jobs-ch]
  (a/go-loop []
    (let [job (a/<! jobs-ch)]
      ; VALIDATION: SMELL START - Misuse of Channel Closing Semantics
      ; VALIDATION: Using :done sentinel value instead of checking if channel is closed
      (when-not (= job :done)
        (println "Processing" job)
        (recur)))))
      ; VALIDATION: SMELL END
```""",
"""```Clojure
(ns async.producer
  (:require [clojure.core.async :as a]))

(defn produce-data [ch]
  (a/go
    (dotimes [i 10]
      (a/>! ch i))
    ; VALIDATION: SMELL START - Misuse of Channel Closing Semantics
    ; VALIDATION: Putting a sentinel :eof to close
    (a/>! ch :eof)))
    ; VALIDATION: SMELL END
```""",
"""```Clojure
(ns async.stream
  (:require [clojure.core.async :as a]))

(defn consume-stream [ch]
  (a/go-loop []
    (let [v (a/<! ch)]
      ; VALIDATION: SMELL START - Misuse of Channel Closing Semantics
      ; VALIDATION: Using ::end as a sentinel
      (if (= v ::end)
        (println "Stream ended")
        (do
          (println "Value:" v)
          (recur))))))
      ; VALIDATION: SMELL END
```""",
"""```Clojure
(ns async.tasks
  (:require [clojure.core.async :as a]))

(defn start-tasks [ch]
  (a/go
    (a/>! ch {:task "A"})
    (a/>! ch {:task "B"})
    ; VALIDATION: SMELL START - Misuse of Channel Closing Semantics
    ; VALIDATION: Passing :stop explicitly
    (a/>! ch :stop)))
    ; VALIDATION: SMELL END
```""",
"""```Clojure
(ns async.manual
  (:require [clojure.core.async :as a]))

(defn feed [ch]
  (a/go
    (a/>! ch 1)
    (a/>! ch 2)
    ; VALIDATION: SMELL START - Misuse of Channel Closing Semantics
    ; VALIDATION: Manually putting nil is an error in core.async, but sometimes attempted as sentinel
    (a/put! ch nil)))
    ; VALIDATION: SMELL END
```"""
        ],
        "goods": []
    },
    "refs_in_dependency_vector": {
        "metadata": {
            "name": "Refs in Dependency Vector",
            "loc": "Function `my-component`",
            "forms": "`r/use-effect`",
            "expl_bad": "Passing a Reagent atom directly in a dependency vector doesn't trigger reactivity properly; it should be dereferenced.",
        },
        "bads": [
"""```Clojure
(ns ui.component
  (:require [reagent.core :as r]))

(defn my-component []
  (let [count-state (r/atom 0)]
    (fn []
      ; VALIDATION: SMELL START - Refs in Dependency Vector
      ; VALIDATION: Using Reagent atom in dependency vector without dereferencing
      (r/use-effect
       (fn [] (println "Count changed"))
       [count-state])
      ; VALIDATION: SMELL END
      [:div "Count: " @count-state])))
```""",
"""```Clojure
(ns ui.dashboard
  (:require [reagent.core :as r]))

(defn dashboard []
  (let [user (r/atom {:name "Alice"})]
    (fn []
      ; VALIDATION: SMELL START - Refs in Dependency Vector
      ; VALIDATION: r/atom passed directly as dependency
      (r/use-effect
       (fn [] (println "User changed"))
       [user])
      ; VALIDATION: SMELL END
      [:div "Hello " (:name @user)])))
```""",
"""```Clojure
(ns ui.settings
  (:require [reagent.core :as r]))

(defn settings-panel []
  (let [theme (r/atom "dark")]
    (fn []
      ; VALIDATION: SMELL START - Refs in Dependency Vector
      ; VALIDATION: Dependency vector contains an atom ref instead of its value
      (r/use-effect
       (fn [] (.setAttribute js/document.body "theme" @theme))
       [theme])
      ; VALIDATION: SMELL END
      [:div "Theme: " @theme])))
```""",
"""```Clojure
(ns ui.search
  (:require [reagent.core :as r]))

(defn search-bar []
  (let [query (r/atom "")]
    (fn []
      ; VALIDATION: SMELL START - Refs in Dependency Vector
      ; VALIDATION: Dependency vector contains [query] instead of [@query]
      (r/use-effect
       (fn [] (println "Searching for:" @query))
       [query])
      ; VALIDATION: SMELL END
      [:input {:on-change #(reset! query (.. % -target -value))}])))
```""",
"""```Clojure
(ns ui.counter
  (:require [reagent.core :as r]))

(defn counter-widget []
  (let [timer (r/atom 0)]
    (fn []
      ; VALIDATION: SMELL START - Refs in Dependency Vector
      ; VALIDATION: Using atom reference as dependency instead of value
      (r/use-effect
       (fn [] (println "Timer tick"))
       [timer])
      ; VALIDATION: SMELL END
      [:div @timer])))
```"""
        ],
        "goods": []
    },
    "improper_emptiness_check": {
        "metadata": {
            "name": "Improper Emptiness Check",
            "loc": "Function `process-items`",
            "forms": "`empty?`",
            "expl_bad": "Using `(not (empty? coll))` or `(when-not (empty? coll) ...)` is unidiomatic and slower than using `seq`.",
            "expl_good": "Use `(seq coll)` or `(when (seq coll) ...)` to check if a collection is non-empty."
        },
        "bads": [
"""```Clojure
(ns data.processor)

(defn process-items [items]
  ; VALIDATION: SMELL START - Improper Emptiness Check
  ; VALIDATION: Using (not (empty? ...)) instead of (seq ...)
  (if (not (empty? items))
    (println "Processing" (count items) "items")
    (println "No items to process")))
  ; VALIDATION: SMELL END
```""",
"""```Clojure
(ns api.handler)

(defn handle-request [req]
  (let [params (:params req)]
    ; VALIDATION: SMELL START - Improper Emptiness Check
    ; VALIDATION: when-not (empty? ...) is better expressed as when (seq ...)
    (when-not (empty? params)
      (println "Has params:" params))))
    ; VALIDATION: SMELL END
```""",
"""```Clojure
(ns report.generator)

(defn generate [data]
  ; VALIDATION: SMELL START - Improper Emptiness Check
  ; VALIDATION: not empty? check
  (cond
    (not (empty? data)) (println "Generating...")
    :else (println "Done")))
  ; VALIDATION: SMELL END
```"""
        ],
        "goods": [
"""```Clojure
(ns data.processor)

(defn process-items [items]
  (if (seq items)
    (println "Processing" (count items) "items")
    (println "No items to process")))
```""",
"""```Clojure
(ns api.handler)

(defn handle-request [req]
  (let [params (:params req)]
    (when (seq params)
      (println "Has params:" params))))
```"""
        ]
    },
    "unnecessary_into": {
        "metadata": {
            "name": "Unnecessary into",
            "loc": "Function `process`",
            "forms": "`into`",
            "expl_bad": "Using `into` to convert a collection when a simpler, more direct function like `vec` or `set` exists.",
            "expl_good": "Use `vec`, `set`, or `update-vals` instead of `into` for simpler conversions."
        },
        "bads": [
"""```Clojure
(ns data.transform)

(defn get-ids [records]
  ; VALIDATION: SMELL START - Unnecessary into
  ; VALIDATION: Using (into [] ...) instead of vec
  (into [] (map :id records)))
  ; VALIDATION: SMELL END
```""",
"""```Clojure
(ns users.permissions)

(defn get-roles [user]
  ; VALIDATION: SMELL START - Unnecessary into
  ; VALIDATION: Using (into #{} ...) instead of set
  (into #{} (:roles user)))
  ; VALIDATION: SMELL END
```""",
"""```Clojure
(ns config.loader)

(defn parse-config [m]
  ; VALIDATION: SMELL START - Unnecessary into
  ; VALIDATION: Using into {} map instead of update-vals or zipmap
  (into {} (map (fn [[k v]] [k (clojure.string/upper-case v)]) m)))
  ; VALIDATION: SMELL END
```"""
        ],
        "goods": [
"""```Clojure
(ns data.transform)

(defn get-ids [records]
  (vec (map :id records)))
```""",
"""```Clojure
(ns users.permissions)

(defn get-roles [user]
  (set (:roles user)))
```"""
        ]
    }
}

for smell_id, smell_data in smells.items():
    dir_path = os.path.join(base_path, smell_id)
    os.makedirs(dir_path, exist_ok=True)
    
    meta = smell_data["metadata"]
    name = meta["name"]
    loc = meta["loc"]
    forms = meta["forms"]
    expl_bad = meta.get("expl_bad", "")
    expl_good = meta.get("expl_good", expl_bad)
    
    # Write bad examples
    for i, code in enumerate(smell_data["bads"], 1):
        file_path = os.path.join(dir_path, f"example_bad_{i}.md")
        content = f"""## Metadata

* **Smell name:** {name}
* **Expected smell location:** {loc}
* **Affected forms:** {forms}
* **Short explanation:** {expl_bad}

{code}
"""
        with open(file_path, "w") as f:
            f.write(content)
            
    # Write good examples
    for i, code in enumerate(smell_data["goods"], 1):
        file_path = os.path.join(dir_path, f"example_good_{i}.md")
        content = f"""## Metadata

* **Smell name:** {name}
* **Expected smell location:** {loc}
* **Affected forms:** {forms}
* **Short explanation:** {expl_good}

{code}
"""
        with open(file_path, "w") as f:
            f.write(content)

print("Done creating all smell files.")
