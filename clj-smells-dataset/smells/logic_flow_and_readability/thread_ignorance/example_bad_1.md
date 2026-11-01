## Metadata

* **Smell name:** thread_ignorance
* **Expected smell location:** Function `extract-active-usernames`
* **Affected forms:** `let`
* **Short explanation:** Uses a verbose let chain to process a collection instead of using the ->> threading macro.

```Clojure
(ns users.analytics)

(defn extract-active-usernames [users]
  ; VALIDATION: SMELL START - thread_ignorance
  ; VALIDATION: Verbose let chain that could be simplified with ->>
  (let [active-users (filter :active? users)
        names (map :username active-users)
        sorted-names (sort names)]
    sorted-names))
  ; VALIDATION: SMELL END
```
