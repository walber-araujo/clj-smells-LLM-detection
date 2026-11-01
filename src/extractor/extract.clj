#!/usr/bin/env bb
(require '[rewrite-clj.zip :as z]
         '[clojure.string :as str])

(defn safe-sexpr [loc]
  (try (z/sexpr loc) (catch Exception _ nil)))

(defn find-named-form [zloc target-name]
  (loop [loc zloc]
    (if (z/end? loc)
      nil
      (if (z/list? loc)
        (let [first-node (z/down loc)
              first-sym (safe-sexpr first-node)]
          (if (and (symbol? first-sym) (str/starts-with? (name first-sym) "def"))
            (let [found (loop [n (z/right first-node)]
                          (if-not n
                            nil
                            (let [s (safe-sexpr n)]
                              (if (symbol? s)
                                s
                                (recur (z/right n))))))]
              (if (= (str found) target-name)
                loc
                (recur (z/next loc))))
            (recur (z/next loc))))
        (recur (z/next loc))))))

(defn find-ns-form [zloc]
  (loop [loc zloc]
    (if (z/end? loc)
      nil
      (if (z/list? loc)
        (let [first-node (z/down loc)
              first-sym (safe-sexpr first-node)]
          (if (= first-sym 'ns)
            loc
            (recur (z/next loc))))
        (recur (z/next loc))))))

(let [[mode file-path element-name] *command-line-args*]
  (if-not (.exists (java.io.File. file-path))
    (do (println "File not found:" file-path) (System/exit 1))
    (try
      (let [zloc (z/of-file file-path)]
        (cond
          (= mode "ns_form")
          (if-let [ns-loc (find-ns-form zloc)]
            (println (z/string ns-loc))
            (System/exit 1))

          (= mode "function")
          (if-let [form-loc (find-named-form zloc element-name)]
            (println (z/string form-loc))
            (System/exit 1))

          :else
          (do (println "Unknown mode:" mode) (System/exit 1))))
      (catch Exception e
        (println "Error parsing file:" (.getMessage e))
        (System/exit 1)))))
