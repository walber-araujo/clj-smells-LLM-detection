## Metadata

* **Smell name:** Namespace Load Side Effects
* **Expected smell location:** Top-level form
* **Affected forms:** `require`, `requiring-resolve`
* **Short explanation:** Using `require` as a top-level form outside the `ns` declaration breaks standard dependency tooling and makes the code harder to reason about.

```Clojure
(ns app.plugins.loader)

; VALIDATION: SMELL START - Namespace Load Side Effects
; VALIDATION: requiring-resolve used at the top-level
(def plugin-init 
  (requiring-resolve 'app.plugins.custom/init))
; VALIDATION: SMELL END

(defn start-plugin []
  (plugin-init))
```
