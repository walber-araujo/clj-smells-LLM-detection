## Metadata

* **Smell name:** unnecessary_laziness
* **Expected smell location:** Function `execute-tasks`
* **Affected forms:** `map`, `doall`
* **Short explanation:** Using lazy `map` for side effects and forcing it with `doall` is less communicative than using eager alternatives like `mapv` or `run!`.

```Clojure
(ns app.tasks.runner)

(defn run-task! [task]
  (println "Running task:" task)
  :done)

(defn execute-tasks
  [tasks]
  ; VALIDATION: SMELL START - unnecessary_laziness
  ; VALIDATION: Using lazy map with side effects and forcing it with doall
  (doall (map run-task! tasks)))
  ; VALIDATION: SMELL END
```
