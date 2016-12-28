/*
 * Copyright (c) 2016 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

import java.io.*;
import java.util.*;

import javax.json.*;

import org.antlr.v4.runtime.*;
import org.antlr.v4.runtime.tree.*;


/**
 * Extended$parser_class is a subclass of the original parser implementation.
 * It can trigger state changes that are needed to identify parts of the input
 * that are not needed to keep it syntactically correct.
 */
public class Extended$parser_class extends $parser_class {

    public static void main(String[] args) {
        try {
            $lexer_class lexer = new $lexer_class(new ANTLRInputStream(new DataInputStream(System.in)));
            CommonTokenStream tokens = new CommonTokenStream(lexer);
            Extended$parser_class parser = new Extended$parser_class(tokens);
            ExtendedTargetListener listener = new ExtendedTargetListener(parser);

            parser.addParseListener(listener);
            Extended$parser_class.class.getMethod(args[0]).invoke(parser);
            parser.syntaxErrorWarning();
            try (JsonWriter w = Json.createWriter(System.out)) {
                w.write(listener.root.createJsonObjectBuilder().build());
            }
        } catch(Exception e) {
            e.printStackTrace(System.err);
            System.exit(1);
        }
    }

    /**
     * ExtendedTargetListener is a subclass of the original listener implementation.
     * It can trigger state changes that are needed to identify parts of the input
     * that are not needed to keep it syntactically correct.
     */
    private static class ExtendedTargetListener extends $listener_class {

        private HDDRule current_node;
        private Parser parser;
        private HDDRule root;

        private static class Position {
            public int line;
            public int column;

            public Position(int _line, int _column) {
                line = _line;
                column = _column;
            }

            public JsonObjectBuilder createJsonObjectBuilder() {
                return Json.createObjectBuilder()
                    .add("line", line)
                    .add("idx", column);
            }
        }

        private static abstract class HDDNode {
            public String name;
            public HDDRule parent;
            public Position start;
            public Position end;

            public HDDNode(String _name) {
                name = _name;
                parent = null;
                start = null;
                end = null;
            }

            public JsonObjectBuilder createJsonObjectBuilder() {
                JsonObjectBuilder builder = Json.createObjectBuilder()
                    .add("type", getClass().getSimpleName())
                    .add("start", start.createJsonObjectBuilder())
                    .add("end", end.createJsonObjectBuilder());
                if (name != null)
                    builder.add("name", name);

                return builder;
            }
        }

        private static class HDDRule extends HDDNode {
            public ArrayList<HDDNode> children;
            public boolean recursive_rule;

            public HDDRule(String _name) {
                super(_name);
                children = new ArrayList<HDDNode>();
                recursive_rule = false;
            }

            public void addChild(HDDNode node) {
                children.add(node);
                node.parent = this;
            }

            public JsonObjectBuilder createJsonObjectBuilder() {
                JsonArrayBuilder children_array = Json.createArrayBuilder();
                for (HDDNode child : children)
                    children_array.add(child.createJsonObjectBuilder());

                return super.createJsonObjectBuilder()
                    .add("children", children_array);
            }
        }

        private static class HDDToken extends HDDNode {
            public String text;

            public HDDToken(String _name, String _text, Position _start, Position _end) {
                super(_name);
                text = _text;
                start = _start;
                end = _end;
            }

            public JsonObjectBuilder createJsonObjectBuilder() {
                return super.createJsonObjectBuilder()
                    .add("text", text);
            }
        }

        private static class HDDQuantifier extends HDDRule {
            public HDDQuantifier() {
                super(null);
            }
        }

        private static class HDDErrorToken extends HDDToken {
            public HDDErrorToken(String _text, Position _start, Position _end) {
                super(null, _text, _start, _end);
            }
        }

        public ExtendedTargetListener(Parser _parser) {
            parser = _parser;
            current_node = null;
            root = null;
        }

        public void recursion_enter() {
            assert current_node instanceof HDDRule;
            HDDRule node = new HDDRule(current_node.name);

            current_node.addChild(node);
            current_node.recursive_rule = true;
            current_node = node;
        }

        public void recursion_push() {
            assert current_node.parent.children.size() > 0;
            HDDNode first_child = current_node.parent.children.get(0);
            current_node.parent.children.remove(first_child);
            current_node.addChild(first_child);
        }

        public void recursion_unroll() {
            assert current_node.recursive_rule;
            assert current_node.children.size() == 1 && current_node.name.equals(current_node.children.get(0).name);
            ArrayList<HDDNode> children_to_lift = ((HDDRule)current_node.children.get(0)).children;
            HDDRule parent = current_node.parent;
            if (children_to_lift.size() > 0) {
                current_node.children = children_to_lift;
                current_node.start = current_node.children.get(0).start;
                current_node.end = children_to_lift.get(current_node.children.size() - 1).end;
            } else {
                current_node = null;
            }
            current_node = parent;
        }

        public void enterEveryRule(ParserRuleContext ctx) {
            HDDRule node = new HDDRule(parser.getRuleNames()[ctx.getRuleIndex()]);

            if (root == null) {
                root = node;
            } else {
                assert current_node != null;
                current_node.addChild(node);
            }
            current_node = node;
        }

        public void exitEveryRule(ParserRuleContext ctx) {
            // If the input contains syntax error, then the last optional block might not have been closed.
            while (current_node instanceof HDDQuantifier)
                exit_optional();

            assert current_node.name.equals(parser.getRuleNames()[ctx.getRuleIndex()]) : current_node.name + " (" + current_node.toString() + ") != " + parser.getRuleNames()[ctx.getRuleIndex()];

            Position[] boundaries = tokenBoundaries(ctx.start);
            current_node.start = boundaries[0];
            current_node.end = ctx.stop == null ? boundaries[1] : tokenBoundaries(ctx.stop)[1];

            if (current_node.parent != null)
                current_node = current_node.parent;
        }

        private Position[] tokenBoundaries(Token token) {
            String text = token.getText();
            int line_breaks = text.length() - text.replace("\n", "").length();
            return new Position[] {new Position(token.getLine(), token.getCharPositionInLine()),
                                   new Position(token.getLine() + line_breaks,
                                                line_breaks == 0 ? token.getCharPositionInLine() + text.length() : text.length() - text.lastIndexOf("\n"))};
        }

        public void visitTerminal(TerminalNode ctx) {
            String name = null;
            String text = null;

            if (ctx.getSymbol().getType() == Token.EOF) {
                name = "EOF";
                text = "";
            } else {
                name = parser.getTokenNames()[ctx.getSymbol().getType()];
                text = ctx.getSymbol().getText();
            }

            Position[] boundaries = tokenBoundaries(ctx.getSymbol());
            current_node.addChild(new HDDToken(name, text, boundaries[0], boundaries[1]));
        }

        public void visitErrorNode(ErrorNode node) {
            if (node.getSymbol() != null) {
                String text = node.getText();
                Position[] boundaries = tokenBoundaries(node.getSymbol());
                current_node.addChild(new HDDErrorToken(text, boundaries[0], boundaries[1]));
            }
        }

        public void enter_optional() {
            HDDQuantifier quant_node = new HDDQuantifier();
            current_node.addChild(quant_node);
            current_node = quant_node;
        }

        public void exit_optional() {
            assert current_node.parent != null : "Quantifier node has no parent.";
            assert current_node.children.size() > 0 : "Quantifier node has no children.";

            current_node.start = current_node.children.get(0).start;
            current_node.end = current_node.children.get(current_node.children.size() - 1).end;
            current_node = current_node.parent;
        }
    }

    public Extended$parser_class(TokenStream input) {
        super(input);
    }

    public void enter_optional() {
        trigger_listener("enter_optional");
    }

    public void exit_optional() {
        trigger_listener("exit_optional");
    }

    public void enterRecursionRule(ParserRuleContext localctx, int state, int ruleIndex, int precedence) {
        super.enterRecursionRule(localctx, state, ruleIndex, precedence);
        trigger_listener("recursion_enter");
    }

    public void enterRecursionRule(ParserRuleContext localctx, int ruleIndex) {
        super.enterRecursionRule(localctx, ruleIndex);
        trigger_listener("recursion_enter");
    }

    public void pushNewRecursionContext(ParserRuleContext localctx, int state, int ruleIndex) {
        super.pushNewRecursionContext(localctx, state, ruleIndex);
        trigger_listener("recursion_push");
    }

    public void unrollRecursionContexts(ParserRuleContext _parentctx) {
        super.unrollRecursionContexts(_parentctx);
        trigger_listener("recursion_unroll");
    }

    private void trigger_listener(String event) {
        for (ParseTreeListener listener : getParseListeners()) {
            try {
                ExtendedTargetListener.class.getMethod(event).invoke(listener);
            } catch (Exception e) {
                System.err.println(e);
            }
        }
    }

    private void syntaxErrorWarning() {
        if (_syntaxErrors > 0)
            System.err.println("$parser_class finished with " + _syntaxErrors + " syntax errors. This may decrease quality.");
    }
}
